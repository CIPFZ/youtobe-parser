import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self):
        self.proxies = self._parse_proxies()
        self.current_index = 0
        
    def _parse_proxies(self) -> list[str]:
        if not settings.PROXY_LIST or settings.PROXY_LIST.strip() == "":
            return []
        # Split by comma
        proxies = [p.strip() for p in settings.PROXY_LIST.split(",") if p.strip()]
        logger.info(f"Loaded {len(proxies)} proxies from configuration.")
        return proxies

    def get_proxy(self) -> Optional[str]:
        """
        Returns the current proxy. If no proxies are configured, returns None.
        """
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index]
        return proxy
        
    def get_all_proxies(self) -> list[str]:
        return self.proxies

    def report_failure(self, failed_proxy: str):
        """
        Report that a proxy failed. This will advance to the next proxy.
        """
        if not self.proxies:
            return
            
        current_proxy = self.proxies[self.current_index]
        if current_proxy == failed_proxy:
            logger.warning(f"Proxy failed: {failed_proxy}. Switching to next proxy.")
            self.current_index = (self.current_index + 1) % len(self.proxies)
            logger.info(f"Now using proxy: {self.proxies[self.current_index]}")

    def add_proxy(self, proxy_url: str) -> bool:
        """
        Add a new proxy. Returns True if added, False if it already exists.
        """
        proxy_url = proxy_url.strip()
        if proxy_url and proxy_url not in self.proxies:
            self.proxies.append(proxy_url)
            logger.info(f"Added proxy: {proxy_url}. Total proxies: {len(self.proxies)}")
            return True
        return False

    def remove_proxy(self, proxy_url: str) -> bool:
        """
        Remove a proxy. Returns True if removed, False if not found.
        """
        proxy_url = proxy_url.strip()
        if proxy_url in self.proxies:
            idx = self.proxies.index(proxy_url)
            self.proxies.pop(idx)
            # Adjust current_index if we removed the active proxy or a proxy before it
            if self.current_index >= len(self.proxies):
                self.current_index = 0
            elif idx < self.current_index:
                self.current_index -= 1
            logger.info(f"Removed proxy: {proxy_url}. Total proxies left: {len(self.proxies)}")
            return True
        return False

proxy_manager = ProxyManager()
