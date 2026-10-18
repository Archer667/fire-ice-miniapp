let csrf = '';
export const setCsrf = value => { csrf = value || ''; };
export const getCsrf = () => csrf;
export async function accountRequest(path, body) {
  let response;
  try { response = await fetch('/api/web-auth/' + path, { method: body ? 'POST' : 'GET', credentials:'same-origin', cache:'no-store', headers:{'Content-Type':'application/json','X-Valyria-Client':'web','X-Valyria-CSRF':csrf}, ...(body ? {body:JSON.stringify(body)} : {}) }); }
  catch { throw new Error('ارتباط با سرور برقرار نیست؛ اتصال اینترنت را بررسی کنید'); }
  const data = await response.json().catch(()=>({}));
  if (!response.ok) { const error = new Error(typeof data.detail==='string'?data.detail:'اطلاعات واردشده معتبر نیست'); error.status=response.status; throw error; }
  if (data.csrf) setCsrf(data.csrf);
  return data;
}
