# ─── Base: Windows Server Core with Python 3.12 ───────────────────────────────
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["cmd", "/S", "/C"]

# Install Python 3.12 via the official installer (silent)
ADD https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe C:\\python-installer.exe
RUN python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir=C:\\Python312 && \
    del C:\\python-installer.exe

# Verify Python
RUN python --version && pip --version

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR C:\\openagent

# ─── Install dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers (optional — needed only if scrapling tools use Playwright)
RUN python -m playwright install chromium --with-deps

# ─── Copy project files ───────────────────────────────────────────────────────
COPY . .

# ─── Environment defaults (override at runtime via --env-file or -e) ──────────
ENV WORKSPACE_ROOT=C:\\openagent-workspace
ENV UPLOAD_DIR=C:\\openagent-workspace\\uploads
ENV WEB_PORT=3000
ENV API_PORT=8080

# Create workspace directory inside the container
RUN mkdir C:\\openagent-workspace && mkdir C:\\openagent-workspace\\uploads

# ─── Expose ports ─────────────────────────────────────────────────────────────
EXPOSE 8080
EXPOSE 3000
EXPOSE 8000

# ─── Default: start the Scrapling MCP server, API, and Frontend ──
CMD ["startup.bat"]
