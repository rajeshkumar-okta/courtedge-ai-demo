# Basketball Stats AI - Internal SSO Demo 🏀

> **A production-ready demonstration of Internal SSO** featuring OAuth 2.0 Token Exchange with a single authorization server, AI-powered NCAA basketball statistics, and comparison to Cross-App Access patterns.

![Internal SSO](https://img.shields.io/badge/OAuth-Internal%20SSO-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)

## 🎯 What This Demo Shows

This application demonstrates **internal SSO with standard OAuth 2.0 Token Exchange** where:

- ✅ **Single Authorization Server** - Everything handled by Okta (no external auth servers)
- ✅ **Standard Token Exchange** - RFC 8693 without Cross-App Access complexity
- ✅ **AI Agent Registration** - Demonstrates Okta's AI Agent management
- ✅ **MCP Integration** - Model Context Protocol for NCAA basketball data
- ✅ **No ID-JAG Required** - Simple flow because same auth server

### 🆚 Comparison to Cross-App Access (Football Demo)

| Feature | Internal SSO (Basketball) | Cross-App Access (Football) |
|---------|---------------------------|------------------------------|
| **Authorization Servers** | 1 (Okta only) | 2 (Okta + Todo0) |
| **Token Flow** | ID Token → Access Token | ID Token → ID-JAG → Access Token |
| **Complexity** | Simple (4 steps) | Complex (7 steps) |
| **Use Case** | Internal tools, same org | External SaaS, different orgs |
| **ID-JAG Needed** | ❌ No | ✅ Yes |
| **Trust Domain** | Single | Cross-domain |

## 🌟 Why Internal SSO?

### The Internal Use Case

When you build applications that all trust the **same authorization server**, you don't need Cross-App Access complexity:

```
Basketball Agent App → Okta (login) → ID Token
                    ↓
            Token Exchange to Okta
                    ↓
               Access Token
                    ↓
          Call Basketball MCP Server
```

**No cross-domain trust needed!** Everything stays within Okta.

### When to Use Internal SSO vs XAA

**✅ Use Internal SSO When:**
- All apps trust the same authorization server
- You control both the requesting and resource applications
- Internal enterprise tools
- Simpler architecture preferred

**✅ Use Cross-App Access (XAA) When:**
- Different authorization servers (customer IdP + your SaaS)
- Cross-domain trust required
- External third-party integrations
- Need enterprise-level visibility across domains

## 🏗️ Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────┐
│                    User Browser                     │
│                                                     │
│  ┌────────────────────────────────────────────┐     │
│  │  Basketball Stats AI (React)               │     │
│  │  • AI-powered chat interface               │     │
│  │  • NCAA basketball queries                 │     │
│  └────────────────────────────────────────────┘     │
└───────────────────┬─────────────────────────────────┘
                    │
                    │ HTTPS
                    ▼
┌────────────────────────────────────────────────────┐
│      Basketball Agent (Next.js - Port 3001)        │
│  ┌──────────────────────────────────────────────┐  │
│  │  NextAuth.js OAuth Client                    │  │
│  │  • OpenID Connect to Okta                    │  │
│  │  • Session Management                        │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Token Exchange Client                       │  │
│  │  • RFC 8693 Token Exchange                   │  │
│  │  • No ID-JAG (same auth server)              │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  MCP Client                                  │  │
│  │  • Spawns Basketball MCP Server              │  │
│  │  • JSON-RPC communication                    │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Claude AI Integration                       │  │
│  │  • Anthropic API                             │  │
│  │  • Tool use with MCP                         │  │
│  └──────────────────────────────────────────────┘  │
└────┬───────────────────┬───────────────────────────┘
     │                   │
     │ ① OAuth Login     │ ② MCP Queries
     │                   │
     ▼                   ▼
┌─────────────┐    ┌──────────────────────┐
│  Okta IdP   │    │  Basketball MCP      │
│             │    │  Server (Node.js)    │
│ • Agent     │    │                      │
│   Auth      │    │  ┌────────────────┐  │
│ • Token     │    │  │ Basketball     │  │
│   Exchange  │    │  │ Tools:         │  │
│             │    │  │ • get_rankings │  │
│             │    │  │ • get_stats    │  │
│             │    │  │ • compare      │  │
│             │    │  └────────────────┘  │
└─────────────┘    └──────────────────────┘
```

### Internal SSO Token Flow (4 Steps)

```
1. User Login
   User → Basketball Agent → Okta
   Result: ID Token

2. Token Exchange
   Basketball Agent → Okta
   Request: ID Token
   Response: Access Token
   (No ID-JAG needed - same auth server!)

3. MCP Query
   Basketball Agent → Basketball MCP Server
   Uses: Access Token for authentication

4. AI Response
   Claude AI → Basketball Data → User
```

## 📋 Prerequisites

### Required

- **Okta Account** (Production or Preview)
  - Create at: [developer.okta.com](https://developer.okta.com)

- **Node.js** v18.x or later
- **Anthropic Claude API Key** (for AI chat)

### Okta Configuration

You need to create:
1. **OIDC Web Application** for the Basketball Agent
2. **AI Agent Registration** in Okta Directory

## 🚀 Installation

### 1. Clone Repository

```bash
cd /Users/johnc/Documents/internal-ssg
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Build MCP Server

```bash
cd packages/basketball-mcp-server
npm run build
```

### 4. Configure Okta

#### A. Create OIDC Application

1. Log into **Okta Admin Console**
2. Go to **Applications** → **Create App Integration**
3. Choose **OIDC - OpenID Connect**
4. Application type: **Web Application**
5. Grant types:
   - ✅ Authorization Code
   - ✅ Refresh Token
   - ✅ Token Exchange (**Important!**)
6. Sign-in redirect URI: `http://sportsstatsgather.com:3001/api/auth/callback/okta`
7. Sign-out redirect URI: `http://sportsstatsgather.com:3001`
8. Save and copy **Client ID** and **Client Secret**

#### B. Register AI Agent

1. Go to **Directory** → **AI Agents**
2. Click **Register AI Agent**
3. Name: "Basketball Stats AI Agent"
4. Assign **owner** (yourself)
5. Add **credentials** (let Okta generate public/private key pair)
6. **Link to OIDC app** created in step A
7. **Activate** the agent

#### C. Create Managed Connection

1. In the AI Agent settings
2. Create **managed connection**
3. Select **authorization server**: Your Okta org authorization server
4. Define **allowed scopes**: `openid`, `profile`, `email`
5. Save

### 5. Configure Environment Variables

```bash
cd packages/basketball-agent
cp .env.local.example .env.local
```

Edit `.env.local`:

```bash
# Anthropic Claude API Key
ANTHROPIC_API_KEY=your_claude_api_key_here

# Okta Configuration
OKTA_CLIENT_ID=your_okta_client_id
OKTA_CLIENT_SECRET=your_okta_client_secret
OKTA_ISSUER=https://your-org.okta.com
OKTA_DOMAIN=your-org.okta.com

# NextAuth
NEXTAUTH_SECRET=$(openssl rand -base64 32)
NEXTAUTH_URL=http://sportsstatsgather.com:3001

# MCP Server Path
MCP_SERVER_PATH=../basketball-mcp-server/dist/server.js

# Public Environment Variables
NEXT_PUBLIC_OKTA_ISSUER=https://your-org.okta.com
NEXT_PUBLIC_APP_NAME=Basketball Stats AI
NEXT_PUBLIC_APP_PORT=3001
```

### 6. Run Locally (for testing)

```bash
cd packages/basketball-agent
npm run dev
```

Open: **http://localhost:3001**

## 🌐 Production Deployment (Ubuntu Server)

### Deploy to sportsstatsgather.com:3001

#### Step 1: Transfer Files to Server

```bash
# From your local machine
scp -r /Users/johnc/Documents/internal-ssg betadmin@sportsstatsgather.com:~/
```

#### Step 2: Server Setup

```bash
# SSH into server
ssh betadmin@sportsstatsgather.com

# Navigate to project
cd ~/internal-ssg

# Install dependencies
npm install

# Build MCP server
cd packages/basketball-mcp-server
npm run build

# Build Next.js app
cd ../basketball-agent
npm run build
```

#### Step 3: Configure Environment

```bash
cd ~/internal-ssg/packages/basketball-agent
nano .env.local
# Add your production environment variables
```

#### Step 4: Create Systemd Service

```bash
sudo nano /etc/systemd/system/basketball-agent.service
```

```ini
[Unit]
Description=Basketball Stats AI Agent (Internal SSO)
After=network.target

[Service]
Type=simple
User=betadmin
WorkingDirectory=/home/betadmin/internal-ssg/packages/basketball-agent
ExecStart=/usr/bin/npm start
Restart=on-failure
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

#### Step 5: Start Service

```bash
sudo systemctl enable basketball-agent
sudo systemctl start basketball-agent

# Check status
sudo systemctl status basketball-agent

# View logs
sudo journalctl -u basketball-agent -f
```

#### Step 6: Verify

Open: **http://sportsstatsgather.com:3001**

## 🎮 Usage

### Basic Flow

1. Navigate to **http://sportsstatsgather.com:3001**
2. Click **Sign in with Okta**
3. Enter your Okta credentials
4. Ask basketball questions:
   - "Who's leading the ACC?"
   - "Compare Duke and North Carolina"
   - "Show me top 10 teams"
   - "What's Kansas's record?"

### Internal SSO Flow Explained

1. **User logs in** → Gets ID token from Okta
2. **Token exchange** → App exchanges ID token for access token (same Okta server)
3. **MCP query** → App calls basketball MCP server with access token
4. **AI response** → Claude processes data and responds

## 🔑 Key Technologies

- **Next.js 14** - App router with server components
- **NextAuth.js** - OAuth authentication
- **Okta OAuth 2.0** - Token exchange (RFC 8693)
- **Model Context Protocol** - AI tool integration
- **Anthropic Claude** - AI language model
- **React** - UI components
- **TypeScript** - Type safety

## 📊 Basketball Data

Data files in `/data`:
- `NCAABTeamRankings.json` - Team statistics and rankings
- `tr_ncaab_team_game_logs.json` - Game-by-game results

## 🐛 Troubleshooting

### "Token Exchange Failed"

**Fix:**
1. Verify `OKTA_CLIENT_ID` and `OKTA_CLIENT_SECRET` are correct
2. Ensure **Token Exchange** grant type is enabled in Okta app
3. Check that AI Agent has a managed connection to the auth server

### OAuth Callback Errors

**Fix:**
1. Verify redirect URI in Okta matches: `http://sportsstatsgather.com:3001/api/auth/callback/okta`
2. Ensure `NEXTAUTH_URL=http://sportsstatsgather.com:3001`
3. Restart the app

### Port Already in Use

**Fix:**
```bash
sudo lsof -i :3001 | grep LISTEN
sudo systemctl stop basketball-agent
```

## 📞 Support

**Issues:** Check systemd logs: `sudo journalctl -u basketball-agent -f`
**Okta Forum:** [devforum.okta.com](https://devforum.okta.com)

## ⚡ Quick Commands

```bash
# Start service
sudo systemctl start basketball-agent

# Stop service
sudo systemctl stop basketball-agent

# Restart service
sudo systemctl restart basketball-agent

# View logs
sudo journalctl -u basketball-agent -f

# Check status
sudo systemctl status basketball-agent
```

---

**Built with ❤️ to demonstrate Internal SSO patterns with Okta** 🏀
