let csrf = '';
export const setCsrf = (token: string) => { csrf = token; };
export async function api(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body) headers.set('Content-Type', 'application/json');
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrf);
  const r = await fetch('/api' + path, { ...options, headers, credentials: 'same-origin' });
  if (!r.ok) {
    let message = '请求失败，请重试';
    try { const j = await r.json(); message = typeof j.detail === 'string' ? j.detail : j.detail?.map((x: any) => `${x.loc?.slice(1).join(' / ')}：${x.msg}`).join('；') || message; } catch {}
    throw new Error(message);
  }
  return r;
}
export async function json(path: string, method = 'GET', data?: unknown) {
  return (await api(path, { method, body: data === undefined ? undefined : JSON.stringify(data) })).json();
}
export async function download(path: string, filename: string, data?: unknown) {
  const r = await api(path, { method: data === undefined ? 'GET' : 'POST', body: data === undefined ? undefined : JSON.stringify(data) });
  const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
}
export function upload(path: string, body: FormData, progress: (n: number) => void): Promise<any> {
  return new Promise((resolve,reject) => {
    const xhr = new XMLHttpRequest(); xhr.open('POST', '/api' + path); xhr.setRequestHeader('X-CSRF-Token', csrf);
    xhr.upload.onprogress = e => { if (e.lengthComputable) progress(Math.round(e.loaded / e.total * 100)); };
    xhr.onerror = () => reject(new Error('上传中断，请检查连接后重试'));
    xhr.onload = () => { try { const j = JSON.parse(xhr.responseText); xhr.status < 300 ? resolve(j) : reject(new Error(typeof j.detail === 'string' ? j.detail : '图片资料格式不正确')); } catch { reject(new Error('上传失败，请重试')); } };
    xhr.send(body);
  });
}
