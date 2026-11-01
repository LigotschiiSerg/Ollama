"""URL download restricted to explicit allowlisted HTTPS hosts."""
from io import BytesIO
from urllib.parse import urlsplit
import requests
from django.conf import settings
from django.core.files.base import ContentFile


def download_pdf(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None,443)
        or not parsed.hostname or parsed.hostname.lower() not in settings.PDF_ALLOWED_HOSTS):
        raise ValueError('Для загрузки URL укажите HTTPS-хост в PDF_ALLOWED_HOSTS')
    # For private installations, only trusted, explicitly allowlisted servers should be configured.
    with requests.get(url,stream=True,timeout=(5,20),allow_redirects=False) as res:
        res.raise_for_status()
        if 300<=res.status_code<400:
            raise ValueError('Переадресация URL запрещена')
        data=BytesIO()
        for chunk in res.iter_content(chunk_size=65536):
            data.write(chunk)
            if data.tell()>settings.PDF_MAX_BYTES:
                raise ValueError('PDF превышает ограничение 20 МБ')
        payload=data.getvalue()
    if not payload.startswith(b'%PDF-'):
        raise ValueError('По ссылке получен не PDF')
    return ContentFile(payload,name='download.pdf')
