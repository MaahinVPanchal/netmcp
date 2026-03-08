# Never commit these (public repo)

Keep all secrets in **environment variables** or **`.env`** (and ensure `.env` is in `.gitignore`). Never commit:

- **PostHog**: `phc_*` project API key (e.g. from PostHog project settings)
- **Supabase**: anon key, service role key (URL alone is often OK in docs)
- **Stripe**: secret key, webhook signing secret
- **AWS**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- **Any** API keys, tokens, or passwords

If a key was ever committed (e.g. in another repo like NovaUI):

1. Rotate/revoke the key in the provider (PostHog, Supabase, etc.).
2. Use the new key only in `.env` or CI secrets, never in code.
3. Consider using GitGuardian or `git secrets` to block future commits.

This repo (Awsmcp/NetMCP) does not use PostHog; the incident you saw was in **NovaUI**. In NovaUI, use `import.meta.env.VITE_POSTHOG_KEY` (or similar) and set the value in `.env` only.
