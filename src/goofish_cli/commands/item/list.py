"""item list — 查看当前账号的在售商品。

打开个人主页 https://www.goofish.com/personal?userId={unb}，
浏览器渲染 + auto_scroll 触发懒加载，提取商品卡片。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from goofish_cli.core import Session, Strategy, command
from goofish_cli.core.browser import auto_scroll, goofish_page
from goofish_cli.core.errors import AuthRequiredError, GoofishError

MAX_LIMIT = 100


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 50
    return min(MAX_LIMIT, max(1, n))


def _item_id_from_url(url: str) -> str:
    m = re.search(r"[?&]id=(\d+)", url or "")
    return m.group(1) if m else ""


_EXTRACT_JS = r"""
(limit) => (async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const waitFor = async (predicate, timeoutMs = 10000) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (predicate()) return true;
      await wait(150);
    }
    return false;
  };

  const clean = (v) => (v || '').replace(/\\s+/g, ' ').trim();

  // 个人主页的商品卡片选择器
  const sel = {
    card: 'a[href*="/item?id="]',
    title: '[class*="title"], [class*="name"]',
    price: '[class*="price"]',
    status: '[class*="status"], [class*="tag"]',
    image: 'img[src*="img.alicdn.com"], img[src*="goofish"]',
  };

  // 等待卡片或空态出现
  await waitFor(() => {
    const bodyText = document.body?.innerText || '';
    return Boolean(
      document.querySelector(sel.card)
      || /请先登录|登录后|验证码|安全验证/.test(bodyText)
      || /暂无商品|还没有发布|没有商品|暂无宝贝/.test(bodyText)
    );
  });

  const bodyText = document.body?.innerText || '';
  const requiresAuth = /请先登录|登录后/.test(bodyText);
  const blocked = /验证码|安全验证|异常访问/.test(bodyText);
  const empty = /暂无商品|还没有发布|没有商品|暂无宝贝|暂无在售/.test(bodyText);

  const items = Array.from(document.querySelectorAll(sel.card))
    .slice(0, limit)
    .map((card) => {
      const href = card.href || card.getAttribute('href') || '';
      const title = clean(card.querySelector(sel.title)?.textContent || '');
      const priceEl = card.querySelector(sel.price);
      const price = clean(priceEl?.textContent || '');
      const img = card.querySelector(sel.image);
      const imageUrl = img ? (img.src || img.getAttribute('data-src') || '') : '';
      // 尝试从标签/角标提取状态（在售/已下架等）
      const tags = Array.from(card.querySelectorAll(sel.status))
        .map(n => clean(n.textContent))
        .filter(Boolean);

      return { title, url: href, price, image_url: imageUrl, tags };
    })
    .filter(it => it.title && it.url);

  return { requiresAuth, blocked, empty, items, bodyPreview: bodyText.slice(0, 500) };
})()
"""


async def _run(limit: int) -> list[dict[str, Any]]:
    session = Session.load()
    url = f"https://www.goofish.com/personal?userId={session.unb}"

    async with goofish_page() as page:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await auto_scroll(page, times=3)
        payload = await page.evaluate(_EXTRACT_JS, limit)

    if not isinstance(payload, dict):
        raise GoofishError("个人主页返回结构非预期")

    items = payload.get("items") or []
    if not items and payload.get("requiresAuth"):
        raise AuthRequiredError("个人主页要求登录，cookies 可能失效")
    if not items and payload.get("blocked"):
        raise GoofishError("个人主页被验证码/安全验证拦截")

    return [
        {
            "rank": i + 1,
            "item_id": _item_id_from_url(it.get("url", "")),
            **it,
        }
        for i, it in enumerate(items)
    ]


@command(
    namespace="item",
    name="list",
    description="查看当前账号的在售商品（浏览器渲染）",
    strategy=Strategy.COOKIE,
    columns=["rank", "item_id", "title", "price", "tags"],
)
def list_items(limit: int = 50) -> dict[str, Any]:
    items = asyncio.run(_run(_normalize_limit(limit)))
    return {"items": items, "total": len(items)}
