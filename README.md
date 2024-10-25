
# Claude Ubuntu OS

Claude Ubuntu OS is an attempt to integrate of Claude's Computer Use API with Ubuntu, enabling AI-powered control over desktop environments. The upgraded Claude 3.5 Sonnet model, introduces a groundbreaking ability to manipulate virtual machines or containerized desktops with security and isolation in mind. It provides seamless interaction with desktop tasks, making automation, management, and even complex workflows more efficient and intelligent.

With  Claude Ubuntu OS, you can execute commands, interact with user interfaces, manipulate files, and more, all under the watchful eye of Claude’s enhanced AI capabilities. This project offers a versatile, sandboxed environment where you can test and run various AI-driven desktop operations, mitigating risk through secure isolation.

## Key Features
- **VNC Desktop Access**: Remotely access and control desktop environments using VNC.
- **Tool Integration**: Supports multiple Anthropic-defined tools like `computer`, `bash`, and `text_editor` to enhance productivity.
- **Agent Loop**: Automates tasks using an intelligent agent loop that evaluates outcomes before proceeding.
- **Security Focused**: Runs in isolated virtual machines or containers to protect sensitive data and prevent unauthorized access.
- **Extensible**: Easily extendable with additional tools and scripts for custom workflows.
- **Interactive AI**: Claude intelligently decides and executes desktop tasks, offering automation with human oversight.

---

## Getting Started

### Prerequisites
To get started with ControlSphere AI, ensure you have the following:
- **Docker** (to run the containerized desktop environment)
- **Fly.io Account** (or any cloud provider for hosting the virtual machine)
- **Anthropic API Key** (for Claude’s API)
- **VNC Client** (for accessing the desktop environment)

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/justmalhar/claude-ubuntu-os.git
   cd claude-ubuntu-os
   ```

2. **Configure Fly.io**:
   - Initialize Fly.io for your project by running:
     ```bash
     flyctl launch
     ```
   - Ensure that ports `5900` (for VNC) and `8080` (for noVNC) are exposed in the `fly.toml` file.

3. **Build and Run the Docker Container**:
   Run the following command to build and deploy the Docker container:
   ```bash
   flyctl deploy
   ```

4. **Set up Anthropic API Key**:
   Export your Anthropic API key to the environment:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key
   ```

### Usage

1. **Access the Desktop**:
   - Use a VNC client to connect to the VNC server on port `5900`.
   - Alternatively, open a browser and navigate to `https://<your-app-name>.fly.dev:8080` to access the desktop via noVNC.

2. **Interact with the Desktop**:
   Once connected, you can send commands to Claude for execution. Example use cases include:
   - Running shell commands via the `bash` tool.
   - Opening and editing files with the `text_editor` tool.
   - Interacting with desktop applications using the `computer` tool.

3. **Agent Loop**:
   Claude will evaluate the results of executed tasks and continue calling tools as needed until the task is complete. This loop ensures that operations are executed step by step, with accuracy.

### Example API Request

Here’s an example of how to use the Anthropic API with the `computer`, `bash`, and `text_editor` tools:

```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "tools": [
      {
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px": 1024,
        "display_height_px": 768,
        "display_number": 1
      },
      {
        "type": "text_editor_20241022",
        "name": "str_replace_editor"
      },
      {
        "type": "bash_20241022",
        "name": "bash"
      }
    ],
    "messages": [
      {
        "role": "user",
        "content": "Open a terminal and list all files in the home directory."
      }
    ]
  }'
```

### Security Considerations

- **Run in an Isolated Environment**: Always run Claude Ubuntu Os in a secure, containerized, or virtualized environment to prevent direct access to your host system.
- **Sensitive Data Protection**: Do not give the AI access to sensitive data or login credentials.
- **Limit Network Exposure**: Restrict internet access and only allow trusted domains to minimize the risk of malicious content.

### Contributing

Feel free to submit issues and pull requests to improve Claude Ubuntu OS. Contributions that enhance security, performance, or extend tool support are especially welcome.

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Make your changes
4. Commit and push your changes (`git push origin feature-branch`)
5. Open a pull request

### License

ControlSphere AI is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
