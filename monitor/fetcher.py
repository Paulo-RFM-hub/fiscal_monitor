import requests
from requests.adapters import HTTPAdapter, Retry
from .utils import clean_html_content


class FetchError(Exception):
    pass


class PageFetcher:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def fetch(self, url, selector=None, raw=False):
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            if raw:
                return response.text
            return clean_html_content(response.text, selector)
        except requests.RequestException as exc:
            raise FetchError(str(exc)) from exc
