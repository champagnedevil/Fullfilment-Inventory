// Scanner variables
let currentCamera = 'environment';
let isScanning = false;
let quaggaInitialized = false;

// Modal management
class ModalManager {
    constructor() {
        this.modals = {};
        this.init();
    }

    init() {
        // Initialize all modals
        this.modals.item = document.getElementById('itemModal');
        this.modals.scanner = document.getElementById('scannerModal');
        this.modals.manualInput = document.getElementById('manualInputModal');
        this.modals.quantity = document.getElementById('quantityModal');
        this.modals.zone = document.getElementById('zoneModal');
        this.modals.box = document.getElementById('boxModal');

        // Close modals when clicking outside
        Object.values(this.modals).forEach(modal => {
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        this.hide(modal);
                    }
                });
            }
        });

        // Back button
        const backButton = document.getElementById('backButton');
        if (backButton) {
            backButton.addEventListener('click', () => window.history.back());
        }
    }

    show(modal) {
        if (modal) {
            modal.style.display = 'block';
        }
    }

    hide(modal) {
        if (modal) {
            modal.style.display = 'none';
            if (modal === this.modals.scanner) {
                this.stopScanner();
            }
        }
    }

    // Scanner functions
    startScanner(forInput = false) {
        this.show(this.modals.scanner);
        this.initializeScanner(forInput);
    }

    stopScanner() {
        isScanning = false;
        if (window.Quagga && quaggaInitialized) {
            try {
                window.Quagga.offDetected();
                window.Quagga.offProcessed();
                window.Quagga.stop();
                quaggaInitialized = false;
            } catch (e) {
                console.log('Scanner already stopped');
            }
        }
        const resultDiv = document.getElementById('scanner-result');
        if (resultDiv) resultDiv.innerHTML = '';
    }

    initializeScanner(forInput = false) {
        const scannerContainer = document.getElementById('scanner-overlay');
        const resultDiv = document.getElementById('scanner-result');
        
        if (!scannerContainer || !resultDiv) return;

        scannerContainer.innerHTML = '';
        resultDiv.innerHTML = '<div class="scanner-status scanning">Наведите камеру на штрих-код...</div>';
        
        isScanning = true;

        // Базовая конфигурация камеры без увеличения
        const config = {
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: scannerContainer,
                constraints: {
                    facingMode: currentCamera,
                    width: { min: 640, ideal: 1280 },
                    height: { min: 480, ideal: 720 }
                }
            },
            decoder: {
                readers: [
                    "code_128_reader",
                    "ean_reader", 
                    "ean_8_reader",
                    "code_39_reader",
                    "upc_reader",
                    "upc_e_reader"
                ]
            },
            locator: {
                patchSize: "medium",
                halfSample: true
            },
            locate: true,
            numOfWorkers: 2,
            frequency: 10
        };

        // Clear previous event listeners
        if (window.Quagga) {
            window.Quagga.offDetected();
            window.Quagga.offProcessed();
        }

        // Initialize Quagga
        window.Quagga.init(config, (err) => {
            if (err) {
                console.error("Scanner init error:", err);
                resultDiv.innerHTML = `
                    <div class="scanner-status error">
                        Ошибка инициализации камеры<br>
                        Пожалуйста, используйте ручной ввод.
                    </div>
                `;
                return;
            }
            
            quaggaInitialized = true;
            window.Quagga.start();
            console.log("Scanner started successfully");
            
            // Add scanning guidance
            resultDiv.innerHTML = `
                <div class="scanner-status scanning">
                    Камера запущена<br>
                    <small>Поднесите штрих-код к камере</small>
                </div>
            `;
        });

        // Detection handler
        window.Quagga.onDetected((result) => {
            if (!isScanning || !result?.codeResult?.code) return;
            
            const code = result.codeResult.code;
            const format = result.codeResult.format || 'unknown';
            
            console.log("Detected barcode:", code, "Format:", format);

            // Validate barcode
            if (!this.isValidBarcode(code)) {
                console.log("Invalid barcode format:", code);
                return;
            }

            // Show success message
            resultDiv.innerHTML = `
                <div class="scanner-status success">
                    ✓ Штрих-код найден!<br>
                    <strong>${code}</strong>
                </div>
            `;
            
            isScanning = false;
            
            // Process after short delay
            setTimeout(() => {
                this.stopScanner();
                this.hide(this.modals.scanner);
                
                if (forInput) {
                    document.getElementById('barcode').value = code;
                    this.showAddItemModal();
                } else {
                    this.showQuantityModal(code);
                }
            }, 800);
        });

        // Processed handler for visual feedback
        window.Quagga.onProcessed((result) => {
            if (!result) return;
            
            const drawingCtx = window.Quagga.canvas.ctx.overlay;
            const drawingCanvas = window.Quagga.canvas.dom.overlay;

            if (drawingCtx) {
                drawingCtx.clearRect(0, 0, parseInt(drawingCanvas.getAttribute("width")), parseInt(drawingCanvas.getAttribute("height")));
                
                // Draw bounding box if detected
                if (result.box) {
                    drawingCtx.strokeStyle = "#00FF00";
                    drawingCtx.lineWidth = 3;
                    drawingCtx.strokeRect(result.box[0], result.box[1], result.box[2], result.box[3]);
                }

                // Draw crosshair in center
                const centerX = parseInt(drawingCanvas.getAttribute("width")) / 2;
                const centerY = parseInt(drawingCanvas.getAttribute("height")) / 2;
                
                drawingCtx.strokeStyle = "#FF0000";
                drawingCtx.lineWidth = 2;
                
                // Horizontal line
                drawingCtx.beginPath();
                drawingCtx.moveTo(centerX - 20, centerY);
                drawingCtx.lineTo(centerX + 20, centerY);
                drawingCtx.stroke();
                
                // Vertical line
                drawingCtx.beginPath();
                drawingCtx.moveTo(centerX, centerY - 20);
                drawingCtx.lineTo(centerX, centerY + 20);
                drawingCtx.stroke();
                
                // Center circle
                drawingCtx.beginPath();
                drawingCtx.arc(centerX, centerY, 8, 0, 2 * Math.PI);
                drawingCtx.stroke();
            }
        });
    }

    // Barcode validation
    isValidBarcode(code) {
        if (!code || typeof code !== 'string') return false;
        
        const cleanCode = code.trim();
        if (cleanCode.length < 3 || cleanCode.length > 50) return false;
        
        // Basic validation - allow most common barcode characters
        return /^[0-9A-Za-z\-\.\$\+\%\/\s]+$/.test(cleanCode);
    }

    switchCamera() {
        currentCamera = currentCamera === 'environment' ? 'user' : 'environment';
        this.stopScanner();
        setTimeout(() => this.startScanner(false), 500);
    }

    // Item modal functions
    showAddItemModal() {
        document.getElementById('itemModalTitle').textContent = 'Добавить товар';
        document.getElementById('itemForm').reset();
        document.getElementById('itemId').value = '';
        document.getElementById('quantity').value = 1;
        this.show(this.modals.item);
    }

    showEditItemModal(itemId, productName, quantity, barcode) {
        document.getElementById('itemModalTitle').textContent = 'Редактировать товар';
        document.getElementById('itemId').value = itemId;
        document.getElementById('productName').value = productName;
        document.getElementById('quantity').value = quantity;
        document.getElementById('barcode').value = barcode || '';
        this.show(this.modals.item);
    }

    // Quantity modal functions
    showQuantityModal(barcode) {
        this.stopScanner();
        
        const checkProduct = async () => {
            try {
                const boxId = document.getElementById('boxId')?.value;
                if (!boxId) return null;
                
                const response = await fetch(`/api/check_product?box_id=${boxId}&barcode=${encodeURIComponent(barcode)}`);
                if (response.ok) {
                    const data = await response.json();
                    return data.exists ? data.product : null;
                }
            } catch (error) {
                console.error('Check product error:', error);
            }
            return null;
        };

        checkProduct().then(existingProduct => {
            document.getElementById('scannedProductName').value = existingProduct ? existingProduct.product_name : `Товар ${barcode}`;
            document.getElementById('scannedBarcode').value = barcode;
            document.getElementById('scannedQuantity').value = 1;
            this.show(this.modals.quantity);
        });
    }

    // Manual input functions
    showManualInput() {
        this.stopScanner();
        this.show(this.modals.manualInput);
        setTimeout(() => {
            const input = document.getElementById('manualBarcodeInput');
            if (input) input.focus();
        }, 100);
    }

    useManualBarcode() {
        const barcode = document.getElementById('manualBarcodeInput')?.value.trim();
        if (!barcode) {
            alert('Введите штрих-код');
            return;
        }

        if (!this.isValidBarcode(barcode)) {
            alert('Неверный формат штрих-кода. Пожалуйста, проверьте введенные данные.');
            return;
        }

        this.hide(this.modals.manualInput);
        document.getElementById('manualBarcodeInput').value = '';
        this.showQuantityModal(barcode);
    }
}

// API functions
class ApiManager {
    static async saveZone() {
        const formData = {
            name: document.getElementById('zoneName').value,
            description: document.getElementById('zoneDescription').value
        };
        
        const zoneId = document.getElementById('zoneId').value;
        const url = zoneId ? `/api/zones/${zoneId}` : '/api/zones';
        const method = zoneId ? 'PUT' : 'POST';
        
        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            if (response.ok) {
                location.reload();
            } else {
                alert('Ошибка при сохранении зоны');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async deleteZone(id) {
        if (!confirm('Удалить зону и все коробки?')) return;
        
        try {
            const response = await fetch(`/api/zones/${id}`, { method: 'DELETE' });
            if (response.ok) location.reload();
            else alert('Ошибка удаления');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async saveBox() {
        const formData = {
            name: document.getElementById('boxName').value,
            description: document.getElementById('boxDescription').value,
            zone_id: document.getElementById('zoneId').value
        };
        
        const boxId = document.getElementById('boxId').value;
        const url = boxId ? `/api/boxes/${boxId}` : '/api/boxes';
        const method = boxId ? 'PUT' : 'POST';
        
        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            if (response.ok) {
                location.reload();
            } else {
                alert('Ошибка при сохранении коробки');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async deleteBox(id) {
        if (!confirm('Удалить коробку и все товары?')) return;
        
        try {
            const response = await fetch(`/api/boxes/${id}`, { method: 'DELETE' });
            if (response.ok) location.reload();
            else alert('Ошибка удаления');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async saveItem() {
        const formData = {
            product_name: document.getElementById('productName').value,
            barcode: document.getElementById('barcode').value,
            quantity: parseInt(document.getElementById('quantity').value),
            box_id: document.getElementById('boxId').value
        };
        
        if (!formData.product_name) {
            alert('Введите название товара');
            return;
        }
        
        const itemId = document.getElementById('itemId').value;
        const url = itemId ? `/api/box_items/${itemId}` : '/api/box_items';
        const method = itemId ? 'PUT' : 'POST';
        
        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            if (response.ok) {
                location.reload();
            } else {
                alert('Ошибка при сохранении товара');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async deleteItem(id) {
        if (!confirm('Удалить товар?')) return;
        
        try {
            const response = await fetch(`/api/box_items/${id}`, { method: 'DELETE' });
            if (response.ok) location.reload();
            else alert('Ошибка удаления');
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async saveScannedItem() {
        const productName = document.getElementById('scannedProductName').value.trim();
        const barcode = document.getElementById('scannedBarcode').value.trim();
        const quantity = parseInt(document.getElementById('scannedQuantity').value);
        const boxId = document.getElementById('boxId')?.value;
        
        if (!productName || !barcode || !quantity || !boxId) {
            alert('Заполните все поля');
            return;
        }
        
        const formData = { product_name: productName, barcode, quantity, box_id: boxId };
        
        try {
            const response = await fetch('/api/box_items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            if (response.ok) {
                modals.hide(modals.modals.quantity);
                location.reload();
            } else {
                alert('Ошибка при добавлении товара');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async exportToExcelAll() {
        try {
            const response = await fetch('/api/export_excel_all');
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `warehouse_export_all_${new Date().toISOString().slice(0,10)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            } else {
                alert('Ошибка при выгрузке всех данных');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }

    static async exportToExcelBoxes() {
        try {
            const response = await fetch('/api/export_excel_boxes');
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `warehouse_export_boxes_${new Date().toISOString().slice(0,10)}.xlsx`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            } else {
                alert('Ошибка при выгрузке данных по коробкам');
            }
        } catch (error) {
            alert('Ошибка: ' + error.message);
        }
    }
}

// Initialize application
let modals;

document.addEventListener('DOMContentLoaded', function() {
    modals = new ModalManager();
    
    // Item page event listeners
    const addItemButton = document.getElementById('addItemButton');
    if (addItemButton) {
        addItemButton.addEventListener('click', () => modals.showAddItemModal());
    }

    const startScannerButton = document.getElementById('startScannerButton');
    if (startScannerButton) {
        startScannerButton.addEventListener('click', () => modals.startScanner(false));
    }

    const scannerForInputButton = document.getElementById('scannerForInputButton');
    if (scannerForInputButton) {
        scannerForInputButton.addEventListener('click', () => {
            modals.hide(modals.modals.item);
            setTimeout(() => modals.startScanner(true), 300);
        });
    }

    // Edit item buttons
    document.querySelectorAll('.edit-item-button').forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item-id');
            const productName = this.getAttribute('data-product-name');
            const quantity = this.getAttribute('data-quantity');
            const barcode = this.getAttribute('data-barcode');
            modals.showEditItemModal(itemId, productName, quantity, barcode);
        });
    });

    // Delete item buttons
    document.querySelectorAll('.delete-item-button').forEach(btn => {
        btn.addEventListener('click', function() {
            const itemId = this.getAttribute('data-item-id');
            ApiManager.deleteItem(itemId);
        });
    });

    // Scanner modal buttons
    const closeScannerModal = document.getElementById('closeScannerModal');
    if (closeScannerModal) {
        closeScannerModal.addEventListener('click', () => modals.hide(modals.modals.scanner));
    }

    const switchCameraButton = document.getElementById('switchCameraButton');
    if (switchCameraButton) {
        switchCameraButton.addEventListener('click', () => modals.switchCamera());
    }

    const manualBarcodeButton = document.getElementById('manualBarcodeButton');
    if (manualBarcodeButton) {
        manualBarcodeButton.addEventListener('click', () => modals.showManualInput());
    }

    // Manual input modal buttons
    const closeManualInputModal = document.getElementById('closeManualInputModal');
    if (closeManualInputModal) {
        closeManualInputModal.addEventListener('click', () => modals.hide(modals.modals.manualInput));
    }

    const cancelManualInputButton = document.getElementById('cancelManualInputButton');
    if (cancelManualInputButton) {
        cancelManualInputButton.addEventListener('click', () => modals.hide(modals.modals.manualInput));
    }

    const useManualBarcodeButton = document.getElementById('useManualBarcodeButton');
    if (useManualBarcodeButton) {
        useManualBarcodeButton.addEventListener('click', () => modals.useManualBarcode());
    }

    // Quantity modal buttons
    const closeQuantityModal = document.getElementById('closeQuantityModal');
    if (closeQuantityModal) {
        closeQuantityModal.addEventListener('click', () => modals.hide(modals.modals.quantity));
    }

    const cancelQuantityButton = document.getElementById('cancelQuantityButton');
    if (cancelQuantityButton) {
        cancelQuantityButton.addEventListener('click', () => modals.hide(modals.modals.quantity));
    }

    const saveScannedItemButton = document.getElementById('saveScannedItemButton');
    if (saveScannedItemButton) {
        saveScannedItemButton.addEventListener('click', () => ApiManager.saveScannedItem());
    }

    // Item modal buttons
    const closeItemModal = document.getElementById('closeItemModal');
    if (closeItemModal) {
        closeItemModal.addEventListener('click', () => modals.hide(modals.modals.item));
    }

    const cancelItemButton = document.getElementById('cancelItemButton');
    if (cancelItemButton) {
        cancelItemButton.addEventListener('click', () => modals.hide(modals.modals.item));
    }

    const saveItemButton = document.getElementById('saveItemButton');
    if (saveItemButton) {
        saveItemButton.addEventListener('click', () => ApiManager.saveItem());
    }

    // Zone page event listeners
    const addZoneBtn = document.getElementById('addZoneBtn');
    if (addZoneBtn) {
        addZoneBtn.addEventListener('click', () => window.showAddZoneModal());
    }

    const editZoneBtns = document.querySelectorAll('.edit-zone-btn');
    editZoneBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const zoneId = this.getAttribute('data-zone-id');
            const zoneName = this.getAttribute('data-zone-name');
            const zoneDescription = this.getAttribute('data-zone-description');
            window.editZone(zoneId, zoneName, zoneDescription);
        });
    });

    const deleteZoneBtns = document.querySelectorAll('.delete-zone-btn');
    deleteZoneBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const zoneId = this.getAttribute('data-zone-id');
            window.deleteZone(zoneId);
        });
    });

    const closeZoneModal = document.getElementById('closeZoneModal');
    if (closeZoneModal) {
        closeZoneModal.addEventListener('click', () => window.closeZoneModal());
    }

    const cancelZoneBtn = document.getElementById('cancelZoneBtn');
    if (cancelZoneBtn) {
        cancelZoneBtn.addEventListener('click', () => window.closeZoneModal());
    }

    const saveZoneBtn = document.getElementById('saveZoneBtn');
    if (saveZoneBtn) {
        saveZoneBtn.addEventListener('click', () => window.saveZone());
    }

    // Box page event listeners
    const addBoxBtn = document.getElementById('addBoxBtn');
    if (addBoxBtn) {
        addBoxBtn.addEventListener('click', () => window.showAddBoxModal());
    }

    const editBoxBtns = document.querySelectorAll('.edit-box-btn');
    editBoxBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const boxId = this.getAttribute('data-box-id');
            const boxName = this.getAttribute('data-box-name');
            const boxDescription = this.getAttribute('data-box-description');
            window.editBox(boxId, boxName, boxDescription);
        });
    });

    const deleteBoxBtns = document.querySelectorAll('.delete-box-btn');
    deleteBoxBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const boxId = this.getAttribute('data-box-id');
            window.deleteBox(boxId);
        });
    });

    const closeBoxModal = document.getElementById('closeBoxModal');
    if (closeBoxModal) {
        closeBoxModal.addEventListener('click', () => window.closeBoxModal());
    }

    const cancelBoxBtn = document.getElementById('cancelBoxBtn');
    if (cancelBoxBtn) {
        cancelBoxBtn.addEventListener('click', () => window.closeBoxModal());
    }

    const saveBoxBtn = document.getElementById('saveBoxBtn');
    if (saveBoxBtn) {
        saveBoxBtn.addEventListener('click', () => window.saveBox());
    }

    // Export buttons
    const exportExcelAllBtn = document.getElementById('exportExcelAllBtn');
    if (exportExcelAllBtn) {
        exportExcelAllBtn.addEventListener('click', () => ApiManager.exportToExcelAll());
    }

    const exportExcelBoxesBtn = document.getElementById('exportExcelBoxesBtn');
    if (exportExcelBoxesBtn) {
        exportExcelBoxesBtn.addEventListener('click', () => ApiManager.exportToExcelBoxes());
    }

    // Enter key handlers
    document.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const activeModal = document.querySelector('.modal[style="display: block"]');
            if (activeModal) {
                if (activeModal.id === 'zoneModal') window.saveZone();
                else if (activeModal.id === 'boxModal') window.saveBox();
                else if (activeModal.id === 'itemModal') ApiManager.saveItem();
                else if (activeModal.id === 'quantityModal') ApiManager.saveScannedItem();
                else if (activeModal.id === 'manualInputModal') modals.useManualBarcode();
            }
        }
    });

    // Manual barcode input enter key
    const manualBarcodeInput = document.getElementById('manualBarcodeInput');
    if (manualBarcodeInput) {
        manualBarcodeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') modals.useManualBarcode();
        });
    }

    // Card clicks
    document.querySelectorAll('.zone-card, .box-card').forEach(card => {
        card.addEventListener('click', function() {
            const zoneId = this.getAttribute('data-zone-id');
            const boxId = this.getAttribute('data-box-id');
            if (zoneId) window.location.href = `/zone/${zoneId}`;
            if (boxId) window.location.href = `/box/${boxId}`;
        });
    });
    document.addEventListener('DOMContentLoaded', function() {
    const mainContent = document.querySelector('.main');
    if (mainContent) {
        mainContent.classList.add('main-content');
    }
    });
});

// Global functions for other pages
window.showAddZoneModal = function() {
    document.getElementById('zoneModalTitle').textContent = 'Добавить зону';
    document.getElementById('zoneForm').reset();
    document.getElementById('zoneId').value = '';
    document.getElementById('zoneModal').style.display = 'block';
}

window.editZone = function(id, name, description) {
    document.getElementById('zoneModalTitle').textContent = 'Редактировать зону';
    document.getElementById('zoneId').value = id;
    document.getElementById('zoneName').value = name;
    document.getElementById('zoneDescription').value = description;
    document.getElementById('zoneModal').style.display = 'block';
}

window.closeZoneModal = function() {
    document.getElementById('zoneModal').style.display = 'none';
}

window.saveZone = ApiManager.saveZone;
window.deleteZone = ApiManager.deleteZone;

window.showAddBoxModal = function() {
    document.getElementById('boxModalTitle').textContent = 'Добавить коробку';
    document.getElementById('boxForm').reset();
    document.getElementById('boxId').value = '';
    document.getElementById('boxModal').style.display = 'block';
}

window.editBox = function(id, name, description) {
    document.getElementById('boxModalTitle').textContent = 'Редактировать коробку';
    document.getElementById('boxId').value = id;
    document.getElementById('boxName').value = name;
    document.getElementById('boxDescription').value = description;
    document.getElementById('boxModal').style.display = 'block';
}

window.closeBoxModal = function() {
    document.getElementById('boxModal').style.display = 'none';
}

window.saveBox = ApiManager.saveBox;
window.deleteBox = ApiManager.deleteBox;