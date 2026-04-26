# Render Deployment - FGA Environment Variables

## Update Required: Switch to New FGA Store

**Store Name:** ProGear New  
**Store ID:** `01KQ391VCMRKCD0G5XE92HVTQY`

---

## Environment Variables to Update on Render

Go to: **Render Dashboard → Your Backend Service → Environment**

### FGA Configuration (Update These)

| Variable | New Value | Notes |
|----------|-----------|-------|
| `FGA_STORE_ID` | `01KQ391VCMRKCD0G5XE92HVTQY` | New store with full model |
| `FGA_MODEL_ID` | `01KQ3D8YPK0CZPH2JKPZ6AWQS8` | New store model ID |
| `FGA_CLIENT_ID` | `u1ZA9DURrNm3AIQhLZebblzw2txLkrcC` | New store credentials |
| `FGA_CLIENT_SECRET` | `tN4_e9MnndkaUUO6yuSKH6AHrJiGZyEMiUbz5oam0DqyfLzhh-sx8dyCv7_ZSLEM` | New store credentials |
| `FGA_API_TOKEN_ISSUER` | `auth.fga.dev` | **Changed** from `fga.us.auth0.com` |
| `FGA_API_URL` | `https://api.us1.fga.dev` | Same (no change) |
| `FGA_API_AUDIENCE` | `https://api.us1.fga.dev/` | Same (no change) |

---

## After Updating Environment Variables

1. Click **"Save Changes"** in Render
2. Render will auto-redeploy with new values
3. Check deployment logs for FGA connection success

Expected log:
```
INFO:auth.fga_client:FGA client initialized: store=01KQ391VCMRKCD0G5XE92HVTQY
```

---

## Verification

Once deployed, test with a request that triggers FGA check:

**Test:** User with `inventory:write` scope
- Should see FGA check in logs
- Should use new store
- Should use `can_update` permission (not `can_increase_inventory`)

---

## Rollback Plan (If Needed)

If new store has issues, revert to old store:

| Variable | Old Value |
|----------|-----------|
| `FGA_STORE_ID` | `01KNSR7472HW2PAYFR224NAPCY` |
| `FGA_MODEL_ID` | `01KNSR8FRB0CMMN79ZT1M2E9S5` |
| `FGA_API_TOKEN_ISSUER` | `fga.us.auth0.com` |
| `FGA_CLIENT_ID` | (old value from Render) |
| `FGA_CLIENT_SECRET` | (old value from Render) |

---

*Last updated: 2026-04-26*
