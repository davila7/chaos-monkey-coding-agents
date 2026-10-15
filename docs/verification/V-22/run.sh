python3 /p/stub.py & sleep 1
export HOME=/tmp/h AI_GATEWAY_API_KEY=dummy FX_MODEL=anthropic/claude-sonnet-5.5 FX_SKIP_ONBOARDING=1 FX_AUTO_UPGRADE=0 FX_GATEWAY_BASE_URL=http://127.0.0.1:8787 FX_GATEWAY_CHAT_URL=http://127.0.0.1:8787/v1/chat
mkdir -p $HOME /w; cd /w; echo hello > a.txt

python3 /p/client.py
