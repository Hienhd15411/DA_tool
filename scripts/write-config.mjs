// Netlify build: ghi web/config.js từ biến môi trường. KHÔNG bao giờ đưa SERVICE_ROLE key vào đây.
import { writeFileSync } from 'node:fs';
const url = process.env.SUPABASE_URL || '', anon = process.env.SUPABASE_ANON_KEY || '';
if (process.env.SUPABASE_SERVICE_ROLE_KEY && anon === process.env.SUPABASE_SERVICE_ROLE_KEY) throw new Error('SUPABASE_ANON_KEY đang là service role key!');
const demo = process.env.VNQ_DEMO === '1' || !url;
writeFileSync('web/config.js', `window.VNQ_CONFIG = ${JSON.stringify({ SUPABASE_URL: url, SUPABASE_ANON_KEY: anon, DEMO: demo })};\n`);
console.log('web/config.js written', { url, demo });
