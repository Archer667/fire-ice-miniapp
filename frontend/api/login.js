// Web edition uses same-origin backend cookie authentication. No Vercel login proxy.
export default function handler(req,res){res.status(404).json({detail:"Use the web backend"});}
