#!/bin/bash
set -e

DROPLET_IP="165.22.221.18"
DROPLET_PATH="/root/nivesh/stocks"

echo "🚀 Deploying Nivesh update..."

# Step 1 — commit and push from Mac
echo "📦 Committing and pushing to git..."
cd ~/Desktop/nivesh/backend
git add .
git commit -m "${1:-auto update $(date '+%Y-%m-%d %H:%M')}"
git push

# Step 2 — pull and restart on droplet
echo "🔄 Pulling on server and restarting..."
ssh root@$DROPLET_IP "
  git config --global --add safe.directory $DROPLET_PATH &&
  cd $DROPLET_PATH &&
  git pull github main &&
  systemctl restart nivesh &&
  systemctl status nivesh --no-pager -l
"

echo "✅ Deployment complete!"
echo "🌐 Live at http://$DROPLET_IP"
