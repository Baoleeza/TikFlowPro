import httpx

api = 'http://127.0.0.1:8000/api/video/download'
params = {'url': 'https://www.tiktok.com/@scout2015/video/6718335390845095173'}

with httpx.stream('GET', api, params=params, timeout=60.0) as r:
    print('Status:', r.status_code)
    print('Headers:', r.headers.get('content-type'))
    if r.status_code != 200:
        try:
            print('Body:', r.text)
        except Exception as e:
            print('Could not read body:', e)
    else:
        with open('out.mp4', 'wb') as f:
            for chunk in r.iter_bytes(chunk_size=1024*1024):
                if not chunk:
                    break
                f.write(chunk)
                break
        print('Wrote first chunk to out.mp4')
