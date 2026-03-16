***

# 🌌 Autonomous Agent Framework (AAF)

**AAF** is a full-fledged OS-level entity, an asynchronous AI agent, and a multi-agent platform built on a microservice Event-Driven architecture.

While popular solutions bet on lightweightness, TypeScript, and storing logs in text files, **AAF is a heavyweight engineering framework in Python**. It is created for those who need complex graph memory, absolute isolation of executed code, and genuine proactivity.

Most modern Open-Source agents suffer from three problems: amnesia (forgetting context after 5 steps), looping (endless ReAct loops), and dependency hell during installation. **AAF solves them all.**

---
## 🔥 Architectural Features

*   **♾️ Multi-Agent Architecture & CLI Manager:** AAF allows you to deploy and orchestrate any number of independent agents on a single server. Management (creation, authorization, launching, and logging) is handled through a convenient interactive terminal (`aaf.py`). Docker Compose is generated automatically.
*   **🧠 Triple Hybrid Memory (State-of-the-Art):** Unlike frameworks that rely solely on vector search, the AAF system does not lose context. It combines Vector DB (ChromaDB: semantics), PostgreSQL (hard rules and tasks), and a full-fledged **GraphRAG** based on KuzuDB (non-linear associations and agent intuition).
*   **⚡ Asynchronous Event Bus (EventBus):** The agent's brain is completely decoupled from the sensors. Messages from Telegram, system logs, and background tasks fall into a single priority queue. The agent decides what to react to right now and what to leave for later. The agent has 3 independent cycles: event reaction, proactivity, and introspection.
*   **🐝 Agent Swarm System:** The main agent is an orchestrator of autonomous subagents. The brain dynamically spawns specialized "workers" (for OSINT or debugging) and immortal "daemons" (for monitoring), delegating routine tasks to save expensive tokens.
*   **👁️ Multimodality:** Use any text model (Gemini, Claude, GPT, GLM) as the main brain. When receiving photos, voice messages, or stickers, the system automatically passes the media through a dedicated Vision/Audio model (coprocessor) and returns a detailed text description to the brain.
*   **💸 Free Operation (API Rotator):** The built-in key manager uses a Round-Robin algorithm and automatically switches to the next key when limits are reached (429 error).
*   **🛡️ WatchDog & Self-Healing:** If a system module crashes, the agent wakes up with maximum priority, reads the Traceback, and attempts to find a solution to the problem.
*   **🧩 Native Plugin System (Zero-Boilerplate):** Forget about writing JSON schemas for OpenAI Tools manually. Simply drop a Python file into the agent's folder, apply the `@llm_skill` decorator, and the framework automatically generates the schema, validates types, injects environment variables, and wraps everything in a fault-tolerant asynchronous thread. Dependencies (`custom_requirements.txt`) are installed on the fly by Docker.

---
## 🏗 Project Structure
The project uses a strict `src-layout` and is divided into the core and agent profiles:

*   `Agents/` - Your agents' profiles. Inside each profile (e.g., `Agents/VEGA/`):
    *   `.env` - Individual agent API keys.
    *   `config/` - Individual settings and personality prompts.
    *   `workspace/` - Isolated zone for databases, temporary files, and the script sandbox.
*   `src/` - Logic source code (Utils, Databases, Sensors, Brain, Swarm). Shared by all agents.

---
## ⚙️ Installation (Quick Start)

No `pip install`, C++ compiler version conflicts, or manual database configuration. The project is packaged in Docker and deployed via the built-in CLI manager.

**Requirements:** Installed Docker Desktop and Python 3.11+ (only for running the CLI manager on the host).

### Step 1. Cloning the Repository

```bash
git clone https://github.com/th0r3nt/AAF-Autonomous-Agent-Framework-
cd AAF-Autonomous-Agent-Framework-
```

### Step 2. Creating an Agent Profile

Launch the interactive AAF Manager:

```bash
python aaf.py
```

Inside the console, enter the creation command (e.g., for an agent named `LUMI`):
```text
create LUMI
```

*The script will generate the `Agents/LUMI/` folder structure, settings, and prepare Docker.*

### Step 3. Key Configuration

Minimize the console and open the newly created `Agents/LUMI/.env` file. Enter your data:
* `TG_API_ID_AGENT` and `TG_API_HASH_AGENT` (get at https://my.telegram.org/auth).
* `LLM_API_KEY_1` (any number of keys are supported).
* Optional: `TAVILY_API_KEY` (web search) and `OPENWEATHER_API_KEY` (weather).

You can also configure the model, timeouts, and limits in the `Agents/LUMI/config/settings.yaml` file.

### Step 4. Telegram Authorization

Return to the AAF console and enter:
```text
auth LUMI
```

The script will ask for a phone number and a code from Telegram. AAF uses **MTProto (Telethon)** — the agent lives in Telegram as a real user, not a bot. The session file will be securely stored in the agent's profile.

### Step 5. Launch

In the AAF console, enter:
```text
start LUMI
```

That's it! Docker will download the images, spin up the databases, and start your agent. 
To view beautiful color-coded logs in real-time, use the command:
```text
logs LUMI
```

---
### 🧠 Personality Customization (Zero-Code)
You can turn the agent into anyone: from a dry corporate analyst to a sarcastic AI. No need to know Python or stop containers — the context is assembled dynamically.

Simply edit 3 files in the `Agents/<NAME>/config/personality/` folder:
* `SOUL.md` - The core of the personality (who they are, what they want, how they relate to the world).
* `COMMUNICATION_STYLE.md` - Speech rules (whether to use emojis, how to address people).
* `EXAMPLES_OF_STYLE.md` - Dialogue examples for Few-Shot prompting.

---
### 🛡️ Isolation & Security (True Docker-in-Docker)

AAF provides **Enterprise-grade security** utilizing a True DinD (Docker-in-Docker) architecture.

A dedicated, fully isolated `sandbox_engine` service is spun up within the stack. The main agent's brain (`agent_lumi`) does not have direct access to your host's Docker socket. When the agent writes and executes Python scripts, they are sent to the sandbox over an internal network, where a disposable, ephemeral micro-container is created for each script.

**Why this matters:**
1. **Host Safety:** Even if the LLM hallucinates destructive code (e.g., `rm -rf /`), it will only destroy the temporary container inside the sandbox. Your host OS remains 100% safe.
2. **Clean Environment:** Scripts leave no garbage or hung processes behind.
3. **Safe Delegation:** You can confidently task the agent with scraping unknown websites or analyzing suspicious files.

---
### 🧩 Extensibility: Plugins vs Sandbox

AAF provides two fundamentally different code execution mechanisms, covering 100% of use cases.

#### 1. Sandbox — Routine Level
* **How it works:** The agent *autonomously* writes a Python script and sends it to the isolated `sandbox_engine` (Docker-in-Docker).
* **Security:** 100% isolation. The script has no access to the host kernel or databases.
* **Use cases:** Delegating complex math, disposable scraping of "dirty" websites, format conversion, running background daemon watchers.
* **Who writes the code:** The Neural Network (LLM).

#### 2. Plugins (Skills) — Brain Level
* **How it works:** You (the developer) create a `.py` file in the `Agents/<NAME>/plugins/` directory.
* **Security:** 0% isolation. The plugin runs directly in the main AAF core Event Loop.
* **Use cases:** Integration with external APIs (Binance, AWS, Smart Home) requiring secret keys from `.env`. Direct manipulation of vector and graph databases (`memory_manager`). Heavy synchronous computations.
* **Who writes the code:** The Human (Architect).

**How to create your own plugin?**
You don't need to dive into the core source code. Open the automatically generated template at `Agents/<NAME>/plugins/example_plugin.py`. 
Write your function, add the `@llm_skill` decorator, and list any required libraries in `custom_requirements.txt`. On the next startup (`python aaf.py start <NAME>`), Docker will automatically download the dependencies, and the skill will appear in the agent's arsenal.

---
## 🛠 Tech Stack

* **Core:** Python 3.11+, Asyncio, Pydantic, Docker, caffeine
* **Memory:** PostgreSQL (SQLAlchemy + JSONB), ChromaDB (Vector), KuzuDB (Graph)
* **Sensors:** Telethon (MTProto), psutil
* **LLM Engine:** Support for any OpenAI-compatible API (Gemini, GPT, Claude, GLM, DeepSeek, etc.).

You can also check out my Telegram channel: I talk about development in more detail there. t.me/VEGA_and_other_heresy

*Architecture & Code by th0r3nt.*
