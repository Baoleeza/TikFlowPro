from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import yt_dlp
import httpx
import tempfile
import os
import zipfile
import shutil
import time
import random
import urllib.parse
from typing import Optional

app = FastAPI(title="TikFlow Pro API - Optimized for Render")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER FUNCTIONS ---

def _create_temp_cookie_file(cookie_str: str) -> str:
    """Tạo file cookie định dạng Netscape từ chuỗi string khách nhập"""
    fd, path = tempfile.mkstemp(suffix='.txt', text=True)
    with os.fdopen(fd, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        # Giả lập dòng cookie cho tiktok.com
        f.write(f".tiktok.com\tTRUE\t/\tFALSE\t2147483647\tcookie\t{cookie_str}\n")
    return path

def _safe_filename(title: str) -> str:
    s = "".join(c for c in title if (c.isalnum() or c in ' ._-'))
    return s.strip() or 'video'

async def stream_remote_url(url: str):
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream('GET', url, timeout=None) as resp:
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail='CDN TikTok từ chối kết nối')
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    yield chunk
        except httpx.RequestError as re:
            raise HTTPException(status_code=502, detail=f"Lỗi đường truyền: {re}")

# --- API ENDPOINTS ---

@app.get('/favicon.ico')
def favicon():
    return Response(content=b"", media_type='image/x-icon')

@app.get('/api/video/download')
async def api_video_download(url: str = Query(...), cookies: str = Query(None)):
    """Tải 1 video lẻ"""
    # We'll download the single video into a temporary directory and
    # return it as a FileResponse. This is more reliable than proxying
    # the CDN stream which can close connections unexpectedly.
    tmpdir = tempfile.mkdtemp(prefix='tikflow_single_')
    ydl_opts = {
        'format': 'bestvideo*+bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    }

    # Cookies handling (client-provided or static file)
    cookie_path = None
    if cookies:
        cookie_path = _create_temp_cookie_file(cookies)
        ydl_opts['cookiefile'] = cookie_path
    elif os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = _safe_filename(info.get('title', 'video')) + '.mp4'
            # download the file into tmpdir
            ydl.download([url])

        # find the downloaded mp4
        mp4_files = [f for f in os.listdir(tmpdir) if f.lower().endswith('.mp4')]
        if not mp4_files:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(status_code=404, detail='Không tải được video. Kiểm tra lại Link hoặc Cookie.')

        file_path = os.path.join(tmpdir, mp4_files[0])
        return FileResponse(
            file_path,
            media_type='video/mp4',
            filename=title,
            background=BackgroundTask(shutil.rmtree, tmpdir)
        )
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

@app.get('/api/profile/info')
def api_profile_info(url: str = Query(...), cookies: str = Query(None)):
    """Quét lấy tổng số video, Tên kênh và Avatar của Profile"""
    ydl_opts = {'extract_flat': True, 'quiet': True, 'no_warnings': True}
    
    cookie_path = None
    if cookies:
        cookie_path = _create_temp_cookie_file(cookies)
        ydl_opts['cookiefile'] = cookie_path
    elif os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if isinstance(info, dict):
                entries = [e for e in info.get('entries', []) if e]
                total = len(entries)
                # Lấy tên kênh và Avatar
                channel_name = info.get('uploader') or info.get('title') or info.get('channel') or "Kênh TikTok"
                avatar = info.get('thumbnail')
            else:
                total = 1
                channel_name = "Video TikTok"
                avatar = None
                
            return {
                'total_videos': total,
                'channel_name': channel_name,
                'avatar': avatar
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'TikTok chặn quét Profile. Hãy làm theo hướng dẫn dán Cookie ở mục Nâng cao.')
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

@app.get('/api/profile/download')
def api_profile_download(url: str = Query(...), start_index: int = Query(..., ge=1), end_index: int = Query(..., ge=1), cookies: str = Query(None)):
    """Tải ZIP theo khoảng video (Giới hạn 5 bài)"""
    
    # Giới hạn cứng 5 video để bảo vệ RAM server Free
    if (end_index - start_index + 1) > 5:
        raise HTTPException(status_code=400, detail='Bản web chỉ tải tối đa 5 video/lần. Vui lòng mua bản Pro để không giới hạn.')

    if end_index < start_index:
        raise HTTPException(status_code=400, detail='Số kết thúc phải lớn hơn số bắt đầu')

    tmpdir = tempfile.mkdtemp(prefix='tikflow_zip_')
    cookie_path = None
    
    ydl_opts = {
        'format': 'bestvideo*+bestaudio/best',
        'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'ignoreerrors': True,
        'playlist_items': f"{start_index}-{end_index}",
        # Cài đặt delay ngẫu nhiên 2-4 giây để tránh bị ban
        'sleep_interval': 2,
        'max_sleep_interval': 4,
    }

    if cookies:
        cookie_path = _create_temp_cookie_file(cookies)
        ydl_opts['cookiefile'] = cookie_path
    elif os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        zip_path = os.path.join(tmpdir, 'videos.zip')
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            added = 0
            for root, _, files in os.walk(tmpdir):
                for fname in files:
                    if fname == 'videos.zip': continue
                    file_path = os.path.join(root, fname)
                    zf.write(file_path, os.path.relpath(file_path, tmpdir))
                    added += 1

        if added == 0:
            raise HTTPException(status_code=404, detail='Không tải được video. Kiểm tra lại Link hoặc Cookie.')

        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename=f'tiktok_batch_{start_index}_{end_index}.zip',
            background=BackgroundTask(shutil.rmtree, tmpdir)
        )
    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

@app.get('/')
def index():
    if os.path.exists('index.html'):
        return FileResponse('index.html', media_type='text/html')
    return {"status": "TikFlow API is Online"}