@echo off
REM Start Email Management Tool with polling mode enabled
echo Starting Email Management Tool in POLLING mode...
echo IMAP_DISABLE_IDLE=1
echo IMAP_POLL_INTERVAL=15

set IMAP_DISABLE_IDLE=1
set IMAP_POLL_INTERVAL=15

python simple_app.py
