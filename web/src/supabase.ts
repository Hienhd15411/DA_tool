import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isConfigured = Boolean(url && key);

export const supabase: SupabaseClient = isConfigured
  ? createClient(url!, key!, {
      auth: { persistSession: true, autoRefreshToken: true },
    })
  : // placeholder để tránh crash module; các call sẽ fail sau khi user config
    createClient("https://placeholder.supabase.co", "placeholder", {
      auth: { persistSession: false, autoRefreshToken: false },
    });

export const envError = isConfigured
  ? null
  : "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Set env vars trên Netlify → Site settings → Environment variables → Clear cache and redeploy.";
