#!/bin/bash
# =============================================================================
# install_ocr_deps.sh
# Script cài đặt các thư viện OCR cần thiết cho ntp_invoice_collector
# Chạy script này trên Odoo server với quyền root hoặc sudo
#
# Usage:
#   bash install_ocr_deps.sh
#   bash install_ocr_deps.sh /opt/odoo/venv   # custom venv path
# =============================================================================

set -e

VENV_PATH="${1:-/opt/odoo/venv}"
PIP="$VENV_PATH/bin/pip"

echo "=============================================="
echo " NTP Invoice Collector - OCR Dependencies"
echo " Virtualenv: $VENV_PATH"
echo "=============================================="

# Check virtualenv exists
if [ ! -f "$PIP" ]; then
    echo "[ERROR] pip not found at $PIP"
    echo "  Please specify the correct virtualenv path:"
    echo "  bash install_ocr_deps.sh /path/to/venv"
    exit 1
fi

echo ""
echo "[1/4] Installing EasyOCR (primary OCR engine)..."
$PIP install easyocr --quiet
echo "  -> EasyOCR installed OK"

echo ""
echo "[2/4] Installing ddddocr 1.4.11 (secondary OCR engine)..."
$PIP install "ddddocr==1.4.11" --quiet
echo "  -> ddddocr installed OK"

echo ""
echo "[3/4] Installing scipy (for noise removal)..."
$PIP install scipy --quiet
echo "  -> scipy installed OK"

echo ""
echo "[4/4] Verifying installations..."
$VENV_PATH/bin/python -c "
import sys
results = []

try:
    import easyocr
    results.append('  [OK] easyocr')
except ImportError as e:
    results.append('  [FAIL] easyocr: ' + str(e))

try:
    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)
    results.append('  [OK] ddddocr 1.4.11')
except ImportError as e:
    results.append('  [FAIL] ddddocr: ' + str(e))
except Exception as e:
    results.append('  [WARN] ddddocr loaded but: ' + str(e))

try:
    from scipy import ndimage
    results.append('  [OK] scipy')
except ImportError as e:
    results.append('  [FAIL] scipy: ' + str(e))

try:
    from PIL import Image
    results.append('  [OK] Pillow')
except ImportError as e:
    results.append('  [FAIL] Pillow: ' + str(e))

for r in results:
    print(r)

if any('[FAIL]' in r for r in results):
    sys.exit(1)
"

echo ""
echo "=============================================="
echo " Installation complete!"
echo " Now restart Odoo:"
echo "   sudo systemctl restart odoo"
echo " Then update module in Odoo UI:"
echo "   Settings -> Update Apps List -> Upgrade ntp_invoice_collector"
echo "=============================================="
