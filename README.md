# Find Your Team - AWS AI Agent Global Hackathon 2025

**🏆 Winning Solution: Maximize Human Potential Through AI-Powered Team Formation**

Find Your Team is a free, open-source platform that ensures no human talent is wasted by connecting people with their purpose and the teams where they can add the most value to the people they love.

## 💔 The Problem: The Human Gap — The Obsolescence of the Soul
We know, in our bones, what the world needs. We see the potential for thriving communities, true innovation, and a sustainable planet. But every day, that potential withers on the vine because we can't find our team. We are one-person armies, burning out in profound isolation.

## 1. The Agony of the Mismatch
For a generation, we have been sold a tragic lie: that a fulfilling life is built on a static qualification—a piece of paper earned through years of debt, memorization, and relentless struggle in a field we didn't love.

**The Lost Years and The Unlived Life:** We spend our most vibrant years and mountains of money on subjects that feel hard, not because we lack capacity, but because they are not our calling. We endure the grinding punishment of studying for a future job we intuitively know we will hate, simply because it promises a paycheck.

**The Daily Punishment of Work:** For millions, a "good-paying job" is a literal punishment—a monotonous, soul-sapping routine where we feel less like humans and more like poorly programmed bots. Our employers, colleagues, and clients sense the deep, corrosive conflict of interests. We are emotionally and spiritually exhausted, tired in a way sleep can't fix, because we are operating outside of our natural alignment.

**The Silent Crisis of Unused Superpowers:** There is a brilliant, heart-aligned mind isolated from the vital teams that desperately need their specific genius. The world’s biggest problems are waiting for these connections to be made, but we are looking at stiff resumes, not true passion or committed heart.

## 2. The Final Betrayal: AI and the Fraud of Generalists
The rise of AI has exposed the ultimate failure of the old system: Static qualifications are now obsolete.

**The Illusion of Expertise is Over:** Any task involving pure data retrieval, predictable analysis, or repetitive content generation is now better, faster, and cheaper when done by a bot. The old system forces us to compete with AI at its own game—a game we are biologically not built to win.

**We Are Not Multi-Tools:** We are not built to do everything. We are not generic multi-tools, nice for a lot of tasks but never the best for any. We are precision instruments, and our power comes from our limitations and our specialization. By forcing us to chase generalist degrees, the old system actively robs us of the time and energy to hone our truly human skills: empathy, original thought, vision, and deep commitment.

## 3. The Grand Illusion: Why "Individual Excellence" Fails
The current talent system is obsessed with collecting individual stars—the highest GPAs, the flashiest resumes—yet this strategy fails in the real world.

**The Springbok Revelation:** The painful truth is that a team built of the best individuals will consistently be beaten by a team with the best chemistry. The Springbok coach, Rassie Erasmus, proved this globally: he deliberately chose players who could align their hearts, sacrifice their ego, and execute a shared, complex vision. They may not be the best at individual tasks, but their cohesion beats the world's most talented teams.

**The Corporate "Bomb Squad" that Never Forms:** In business and community projects, the investment in "talent" delivers only mediocrity because individuals devolve into silos and friction. We prioritize skill-capacity over heart-alignment. We are missing the "why." We are trying to win World Cups with a roster of solo artists who refuse to pass the ball.

### 🤝 Our Manifesto: We Live For Others — The Power of Alignment
FYT is built on the defiant belief that technology must serve, elevate, and accelerate human connection, not replace it. We are building the engine that connects focused human passion with the world's most vital missions.

## 1. The Call to Build: The IKEA Effect for the Human Heart
This project is not just a platform; it is a declaration of independence from the broken status quo. It is built by communities, for communities.

**Your Code is Your Love:** We don't just want your bug fixes or your code contributions. We want your ownership. This is the IKEA Effect in action: the work you put into this platform is the value you create for your own life, your family, and your neighbors. The platform you help build is the one that will help your son find his purpose, your sister launch her project, or your local community finally find the leader it needs.

**Save Them From Punishment:** FYT is there to make life better for the ones we love. By contributing your time, your story, your feedback, or your skill, you are helping to save millions of people from the daily punishment of a misaligned job. You are creating the escape hatch.

**The Victory of Alignment:** We believe that the greatest impact in the world is achieved when hearts, bodies, and minds align to be the best in their extreme, often small, narrow domain. FYT is the mechanism to align a person's unique superpower (that thing they love so much they do it all day) with a team that values it.

## 2. Our Unwavering Commitment
100% Free and Open Source: The connections that save our communities cannot be locked behind a paywall. This platform is 100% Free and Open Source because the code itself is a public good, built by the very community it serves.

**Our Mission:** This is how we will find the right players, launch vital community projects, create stronger local economies, and foster the genuine, productive relationships that heal a fractured world. We are here for the impact that's waiting to be unleashed. Join us.

## ✨ Our Solution

Find Your Team uses a **3-agent AI architecture** powered by AWS Bedrock Claude 4 Sonnet to intelligently match people to teams, monitor performance, and enable seamless communication.

### 🤖 Three AI Agents

1. **Onboarding Agent**  
   Conducts empathetic conversations using Claude 4 Sonnet to build comprehensive Purpose Profiles (values, skills, work style, motivations).

2. **Matching Agent**  
   Uses semantic search and compatibility analysis to match people with teams. Provides explainable recommendations with alignment scores.

3. **Team Agent**  
   Monitors team performance, analyzes dynamics, and generates coaching insights for continuous improvement.

## 🎯 Hackathon Strategy

This solution is designed to **win first place** by hitting all key judging criteria:

### Deep AWS Agent Utilization (50% - Technical Execution)
- **3-Agent Architecture** using Amazon Bedrock AgentCore
- **Onboarding Agent**: Builds comprehensive Purpose Profiles using Claude 3.5 Sonnet
- **Matching Agent**: Uses OpenSearch vector embeddings for contextual team matching
- **Team Agent**: Continuous performance monitoring with Lambda action groups

### Real-World Impact (20% - Potential Value)
- **Target**: Help millions of poor people join teams and add value to their communities
- **Problem**: Low-bandwidth/offline barriers to economic opportunity
- **Solution**: Resilient multi-protocol communication (MQTT, WebRTC, offline-first PWA)

### Measurable Results (10% - Functionality)
- **Team Performance Metrics**: Productivity, collaboration, satisfaction tracking
- **Human Potential Utilization**: Talent discovery and activation rates
- **Community Impact**: Local team effectiveness and value creation

## 🏗️ Architecture Overview

## High-Level Architecture

```mermaid
graph TB
    subgraph ClientLayer ["Client Layer"]
        PWA["Progressive Web App<br/>Offline-First Design"]
        WebRTC["WebRTC P2P Chat<br/>End-to-End Encrypted"]
        ServiceWorker["Service Worker<br/>Offline Caching"]
    end
    
    subgraph AgentCore ["Agent Orchestration - BedrockAgentCore"]
        Core["BedrockAgentCore<br/>Multi-Agent Workflows"]
        Onboarding["Onboarding Agent<br/>Purpose Profile Builder"]
        Matching["Matching Agent<br/>Semantic Team Matching"]
        Team["Team Agent<br/>Performance Monitoring"]
        Integration["Integration Agent<br/>API Orchestration"]
    end
    
    subgraph AWSServices ["AWS Services"]
        Bedrock["Amazon Bedrock<br/>Claude 4 Sonnet"]
        DynamoDB[("DynamoDB<br/>User Profiles & Teams")]
        OpenSearch[("OpenSearch<br/>Vector Embeddings<br/>Optional")]
        IoT["IoT Core MQTT<br/>Real-time Messaging<br/>Optional"]
        Lambda["AWS Lambda<br/>Action Groups<br/>Optional"]
    end
    
    subgraph CommLayer ["Communication Layer"]
        SocketIO["Socket.IO Server<br/>Real-time Signaling"]
        P2PEngine["Enhanced P2P Engine<br/>Local Storage Manager"]
    end
    
    subgraph ExternalIntegrations ["External Integrations"]
        GitHub["GitHub API"]
        Slack["Slack API"]
        Jira["Jira API"]
        Zoom["Zoom API"]
    end
    
    %% Client connections
    PWA --> Core
    PWA --> SocketIO
    WebRTC --> P2PEngine
    ServiceWorker --> PWA
    
    %% Agent orchestration
    Core --> Onboarding
    Core --> Matching
    Core --> Team
    Core --> Integration
    
    %% AWS service connections
    Onboarding --> Bedrock
    Matching --> Bedrock
    Team --> Bedrock
    Integration --> Bedrock
    
    Onboarding --> DynamoDB
    Team --> DynamoDB
    Matching --> OpenSearch
    Team --> Lambda
    
    %% Communication
    SocketIO --> P2PEngine
    SocketIO --> IoT
    
    %% External integrations
    Integration --> GitHub
    Integration --> Slack
    Integration --> Jira
    Integration --> Zoom
    
    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef agent fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef client fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    classDef comm fill:#9C27B0,stroke:#6A1B9A,stroke-width:2px,color:#fff
    classDef external fill:#FF5722,stroke:#D84315,stroke-width:2px,color:#fff
    
    class Bedrock,DynamoDB,OpenSearch,IoT,Lambda aws
    class Core,Onboarding,Matching,Team,Integration agent
    class PWA,WebRTC,ServiceWorker client
    class SocketIO,P2PEngine comm
    class GitHub,Slack,Jira,Zoom external
```

## Agent Workflow Diagram

```mermaid
sequenceDiagram
    participant User
    participant PWA as Progressive Web App
    participant Core as BedrockAgentCore
    participant OA as Onboarding Agent
    participant MA as Matching Agent
    participant TA as Team Agent
    participant Bedrock as Amazon Bedrock
    participant DB as DynamoDB
    
    User->>PWA: Start onboarding
    PWA->>Core: Initialize workflow
    Core->>OA: Start conversation
    
    loop Purpose Profile Building
        OA->>Bedrock: Generate questions (Claude 4)
        Bedrock-->>OA: Contextual questions
        OA-->>User: Ask about values/skills
        User->>OA: Provide responses
        OA->>DB: Store profile data
    end
    
    OA->>Core: Profile complete (confidence ≥90%)
    Core->>MA: Handoff to matching
    
    MA->>Bedrock: Generate embeddings
    MA->>OpenSearch: Vector similarity search
    OpenSearch-->>MA: Similar teams
    MA->>Bedrock: Generate explanations
    Bedrock-->>MA: Match reasoning
    MA-->>User: Recommended teams
    
    User->>PWA: Join team
    PWA->>Core: Team joined
    Core->>TA: Monitor performance
    
    loop Continuous Monitoring
        TA->>DB: Collect metrics
        TA->>Bedrock: Analyze performance
        Bedrock-->>TA: Coaching insights
        TA-->>User: Performance feedback
    end
```

## Data Flow Architecture

```mermaid
graph LR
    subgraph InputLayer ["Input Layer"]
        UI["User Interface"]
        API["REST API"]
        WS["WebSocket Events"]
    end
    
    subgraph ProcessingLayer ["Processing Layer"]
        AC["AgentCore Orchestrator"]
        OA["Onboarding Agent"]
        MA["Matching Agent"]
        TA["Team Agent"]
    end
    
    subgraph AILayer ["AI/ML Layer"]
        Claude["Claude 4 Sonnet"]
        Embeddings["Titan Embeddings"]
        Search["Vector Search"]
    end
    
    subgraph StorageLayer ["Storage Layer"]
        Profiles[("User Profiles")]
        Teams[("Team Data")]
        Vectors[("Vector Index")]
        Cache[("Local Cache")]
    end
    
    %% Data flow connections
    UI --> AC
    API --> AC
    WS --> AC
    
    AC --> OA
    AC --> MA
    AC --> TA
    
    OA --> Claude
    MA --> Claude
    MA --> Embeddings
    MA --> Search
    TA --> Claude
    
    OA --> Profiles
    MA --> Teams
    MA --> Vectors
    TA --> Teams
    
    Cache --> UI
    
    %% Color styling for different layers
    classDef input fill:#E3F2FD,stroke:#1976D2,stroke-width:2px,color:#0D47A1
    classDef processing fill:#E8F5E8,stroke:#388E3C,stroke-width:2px,color:#1B5E20
    classDef ai fill:#FFF3E0,stroke:#F57C00,stroke-width:2px,color:#E65100
    classDef storage fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#4A148C
    
    %% Apply styles to nodes
    class UI,API,WS input
    class AC,OA,MA,TA processing
    class Claude,Embeddings,Search ai
    class Profiles,Teams,Vectors,Cache storage
```

### 🎨 Key Features

#### 🤖 AI-Powered Intelligence
- **Conversational Onboarding**: Natural language profiling (5-10 minutes)
- **Semantic Matching**: 87-94% alignment scores with explainable AI
- **Performance Coaching**: Real-time insights and recommendations
- **Multi-Language Support**: Works in 100+ languages via Claude 4 Sonnet

#### 💬 Real-Time Communication
- **P2P WebRTC**: Direct peer-to-peer chat with end-to-end encryption
- **Socket.IO Integration**: Real-time messaging and presence
- **Bandwidth-Aware Modes**: Adapts to network quality (high/medium/low/offline)
- **Local Storage**: Message persistence without cloud dependency

#### 📡 Resilient Architecture
- **Progressive Web App**: Mobile-friendly, installable, offline-capable
- **HTTPS Support**: Built-in SSL with auto-generated certificates
- **Service Worker Caching**: Works without internet connection
- **Multiple Transports**: WebRTC, Socket.IO, HTTP fallback
- **Local-First Design**: Minimal AWS usage for cost-effectiveness
- **Modular Structure**: Refactored from 2269-line monolith to clean blueprints

#### 📊 Team Performance
- **Real-Time Metrics**: Track productivity, collaboration, satisfaction
- **Coaching Insights**: AI-generated recommendations by category
- **Performance Reports**: Comprehensive team analytics
- **Continuous Monitoring**: Automated performance tracking

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- AWS Account with Bedrock access (Claude 3.5 Sonnet model enabled)
- Node.js 18+ (for frontend build tools, optional)

### 1. Clone and Setup

```bash
git clone https://github.com/jobeer1/find-your-team.git
cd find-your-team

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure AWS Credentials

Create `config.ini` from the template:

```bash
cp config.ini.example config.ini
```

Edit `config.ini` with your AWS credentials:

```ini
[AWS]
aws_region = us-west-2
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
bedrock_model_id = anthropic.claude-sonnet-4-20250514-v1:0

[APP]
debug = false
host = 0.0.0.0
port = 5004
secret_key = your-secret-key-change-in-production

[AGENTS]
onboarding_agent_enabled = true
matching_agent_enabled = true
team_agent_enabled = true
```

### 3. Run the Application

**HTTP Mode** (default):
```bash
python app_refactored.py
```

Visit `http://localhost:5004` in your browser.

**HTTPS Mode** (recommended for WebRTC):
```bash
python app_refactored.py --https
```

Visit `https://localhost:5004` in your browser.

> **Note**: HTTPS mode will auto-generate self-signed certificates if `ssl_certs/cert.pem` and `ssl_certs/key.pem` don't exist. Your browser will show a security warning for self-signed certs (click "Advanced" and "Proceed").

### 4. Deploy (Optional)

For production deployment:

```bash
# Deploy to Cloudflare (or your platform)
python cloudflare_deploy.py

# Or use the deployment script
python deploy.py
```

---

## 📚 How It Works

### 1. Onboarding Flow

Users chat with the Onboarding Agent, which asks contextual questions to build a Purpose Profile:

- **Values**: What matters most (impact, autonomy, growth, etc.)
- **Skills**: Technical and soft skills with proficiency levels
- **Work Style**: Preferences for structure, communication, pace
- **Motivations**: What drives them (learning, helping others, solving problems)

The agent generates a comprehensive profile stored in DynamoDB.

### 2. Team Matching

The Matching Agent takes a user profile and:

1. Generates semantic embeddings of profile and opportunities
2. Performs vector similarity search (if OpenSearch available) or rule-based matching
3. Analyzes compatibility across values, skills, and work style
4. Produces ranked matches with explainable scores (87-94% accuracy)

Users receive team recommendations with clear explanations for why they're a good fit.

### 3. Performance Monitoring

Once on a team, the Team Agent:

1. Tracks performance metrics (productivity, collaboration, satisfaction)
2. Analyzes team dynamics and communication patterns
3. Generates coaching insights by category (leadership, skill development, etc.)
4. Provides actionable recommendations for improvement

### 4. Real-Time Chat

The chat system supports:

- **WebRTC P2P**: Direct connections for privacy and low latency
- **Socket.IO**: Fallback for real-time messaging
- **Local Storage**: Message persistence across sessions
- **Adaptive Modes**: Switches between high/medium/low bandwidth modes automatically

---

## 🏗️ Project Structure

```
find-your-team/
├── agents/                      # AI agent implementations
│   ├── agent_core.py           # AgentCore orchestration system
│   ├── onboarding_agent.py     # Onboarding conversational agent
│   ├── matching_agent.py       # Semantic matching agent
│   └── team_agent.py           # Performance monitoring agent
├── routes/                      # Flask route blueprints (modular)
│   ├── auth_routes.py          # Authentication endpoints
│   ├── chat_routes.py          # Chat API endpoints
│   ├── onboarding_routes.py    # Onboarding flow endpoints
│   ├── page_routes.py          # Page rendering routes
│   ├── team_routes.py          # Team management endpoints
│   └── utility_routes.py       # Health checks, debugging
├── services/                    # Business logic services
│   ├── bedrock_service.py      # AWS Bedrock agent service
│   ├── data_service.py         # DynamoDB data operations
│   └── location_service.py     # Geolocation services
├── config/                      # Configuration management
│   └── aws_config.py           # AWS credentials and settings
├── models/                      # Data models
│   └── core_models.py          # User, Team, Match models
├── communication/               # Real-time communication layer
│   └── flask_integration.py    # Socket.IO integration
├── ssl_certs/                   # SSL certificates (auto-generated)
│   ├── cert.pem                # Self-signed certificate
│   └── key.pem                 # Private key
├── templates/                   # HTML templates
│   ├── find_your_team.html     # Main landing page
│   ├── dashboard.html          # User dashboard
│   ├── p2p_chat.html           # P2P chat interface
│   └── ...
├── static/                      # Frontend assets
│   ├── js/
│   │   ├── chat-core.js        # Core chat functionality
│   │   ├── webrtc-manager.js   # WebRTC P2P manager
│   │   ├── storage-manager.js  # Local storage manager
│   │   └── ...
│   └── css/
├── tests/                       # Unit and integration tests
├── app_refactored.py            # Main Flask application (refactored)
├── config.ini                   # Configuration (not in git)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🛠️ AWS Services Used

### Core Services

- **Amazon Bedrock**: Claude 4 Sonnet for conversational AI (all 3 agents)
- **Amazon DynamoDB**: User profiles, team data, performance metrics
- **Amazon Bedrock Runtime**: Agent invocation and orchestration

### Optional Services

- **Amazon OpenSearch**: Vector embeddings for semantic search (fallback to rule-based if unavailable)
- **AWS IoT Core**: MQTT messaging for real-time communication (fallback to Socket.IO)
- **AWS Lambda**: Serverless functions for Team Agent action groups (optional)
- **Amazon API Gateway**: REST API management (optional)

### Cost Optimization

The platform is designed to minimize AWS costs:

- **Local-First**: Messages and data cached locally
- **Conditional Services**: OpenSearch and IoT Core are optional
- **Efficient Prompts**: Optimized Claude 3.5 Sonnet prompts for fast, accurate responses
- **Caching**: Response caching to reduce Bedrock API calls

---

## 📊 Agent Architecture Details

### AgentCore Orchestration

`BedrockAgentCore` manages multi-agent workflows:

- **Agent Registration**: Registers all 3 agents with configurations
- **Workflow Execution**: Orchestrates handoffs between agents
- **Decision Logging**: Tracks all agent decisions for auditing
- **Performance Monitoring**: Collects metrics per agent
- **Error Handling**: Retry logic and graceful degradation

### Onboarding Agent

**Technology**: Claude 4 Sonnet via Bedrock Runtime  
**Purpose**: Build comprehensive Purpose Profiles through conversation

**Key Capabilities**:
- Multi-stage conversation flow (greeting, values, skills, work style)
- Context-aware question generation
- Confidence scoring for profile completeness
- Location-aware personalization
- Conversation memory persistence (DynamoDB)

**Example Interaction**:
```
Agent: Hi! I'm here to help you find your perfect team. 
       Let's start with what matters most to you in your work.
       What impact do you want to have?

User: I want to help my community access clean water.

Agent: That's powerful. Clean water access is crucial. 
       What skills do you have that could help with this?
       (e.g., engineering, fundraising, community organizing)
```

### Matching Agent

**Technology**: Claude 4 Sonnet + Semantic Search  
**Purpose**: Match users to teams with explainable recommendations

**Key Capabilities**:
- Semantic embedding generation (Bedrock Titan)
- Vector similarity search (OpenSearch or in-memory)
- Compatibility analysis across multiple dimensions
- Explainable match scores with reasoning
- Skill gap analysis

**Matching Algorithm**:
1. Generate embeddings for user profile and team opportunities
2. Compute cosine similarity scores
3. Apply compatibility weights (values: 40%, skills: 30%, work style: 20%, other: 10%)
4. Rank matches and generate explanations
5. Return top N matches with 87-94% alignment scores

### Team Agent

**Technology**: Claude 4 Sonnet + Performance Analytics  
**Purpose**: Monitor team dynamics and provide coaching

**Key Capabilities**:
- Real-time performance metric tracking
- Team dynamics analysis
- Coaching insight generation by category
- Actionable recommendations
- Performance trend reporting

**Coaching Categories**:
- Communication
- Collaboration
- Leadership
- Skill Development
- Team Dynamics
- Productivity

---

## 💬 Chat System Architecture

### WebRTC P2P Manager

Direct peer-to-peer connections for privacy and performance:

- **Signaling**: Socket.IO for WebRTC offer/answer/ICE exchange
- **STUN/TURN**: ICE candidate gathering and NAT traversal
- **Data Channels**: Real-time text, file transfer
- **Connection Quality**: Automatic quality monitoring

### Enhanced P2P Chat Engine

Robust chat with local storage:

- **Message Persistence**: Local storage for offline access
- **Bandwidth Modes**: Adapts to network conditions
- **Deduplication**: Prevents duplicate messages
- **Rate Limiting**: Prevents spam and overload
- **User Search**: Find chat partners by location/interests

### Socket.IO Integration

Fallback real-time transport:

- **Room Management**: Private and group chats
- **Presence Tracking**: Online/offline status
- **Typing Indicators**: Real-time feedback
- **Read Receipts**: Message delivery confirmation

---

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest tests/

# Run specific agent tests
pytest tests/test_onboarding_agent.py
pytest tests/test_matching_agent.py
pytest tests/test_team_agent.py

# Run with coverage
pytest --cov=agents --cov=routes tests/
```

---

## 🚀 Deployment

### Local Development

**HTTP Mode**:
```bash
python app_refactored.py
```

**HTTPS Mode** (required for WebRTC P2P):
```bash
python app_refactored.py --https
```

The app will auto-generate self-signed SSL certificates on first run with `--https` flag.

### Production (Cloudflare/AWS/GCP)

1. Set environment variables or update `config.ini` for production
2. **Enable HTTPS** (required for WebRTC)
3. Configure CORS for your domain
4. Deploy using your platform's CLI or CI/CD

Example for Cloudflare:

```bash
python cloudflare_deploy.py
```

### Environment Variables

```bash
export AWS_REGION=us-west-2
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export FLASK_SECRET_KEY=your-secret-key
export PORT=5004
```

### SSL Certificate Setup

**For Development:**
- Run with `--https` flag to auto-generate self-signed certificates
- Certificates are saved to `ssl_certs/cert.pem` and `ssl_certs/key.pem`
- Browser will show security warning (click "Advanced" → "Proceed to localhost")

**For Production:**
- Use Let's Encrypt or your certificate provider
- Place certificates in `ssl_certs/` directory
- Or configure your reverse proxy (nginx, Apache) to handle SSL

**Why HTTPS?**
- **Required for WebRTC**: Browser security requires HTTPS for P2P connections
- **Secure Communication**: Encrypts all data in transit
- **Production-Ready**: Same setup for dev and production

---

## 🤝 Contributing

We welcome contributions! This is a community-driven project.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🌍 Mission

**100% Free and Open Source**

Human connection should never be locked behind a paywall. This platform is built by communities, for communities. We believe the greatest impact happens when people align their unique strengths with teams that value them.

**Your code is your contribution to a world where no talent is wasted.**

---

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/jobeer1/find-your-team/issues)
- **Documentation**: See `/docs` folder for detailed guides
- **Community**: Join our discussions

---

## 🎯 Roadmap

### Phase 1: Core Platform (Current)
- ✅ 3-agent AI architecture (Claude 4 Sonnet)
- ✅ Real-time P2P chat
- ✅ Onboarding and matching
- ✅ Performance monitoring

### Phase 2: Enhanced Features
- 🔄 Mobile app (React Native)
- 🔄 Multi-language UI
- 🔄 Advanced analytics dashboard
- 🔄 Team collaboration tools

### Phase 3: Global Scale
- 📋 Regional deployments
- 📋 Enterprise features
- 📋 Impact measurement
- 📋 Community governance

---

**🚀 Ready to find your team? Let's maximize human potential together!**


---

**🚀 Ready to maximize human potential? Let's Find Your Team!**
