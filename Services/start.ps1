# Script de pornire corectă a tuturor serviciilor (Windows PowerShell)
# Rulează cu: .\start.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "🚀 Pornire Microservicii Date Juridice" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Verifică dacă Docker este disponibil
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker nu este instalat sau nu este în PATH" -ForegroundColor Red
    exit 1
}

# Pas 1: Oprește toate containerele vechi
Write-Host "📛 Pas 1/6: Oprire containere vechi..." -ForegroundColor Yellow
docker compose down
Start-Sleep -Seconds 2

# Pas 2: Curăță volume-urile vechi (opțional)
$response = Read-Host "❓ Ștergi datele vechi? (y/n)"
if ($response -eq 'y' -or $response -eq 'Y') {
    Write-Host "🗑️  Ștergere volume-uri vechi..." -ForegroundColor Yellow
    docker compose down -v
    Write-Host "✅ Volume-uri șterse" -ForegroundColor Green
}

# Pas 3: Creează directoarele necesare
Write-Host "📁 Pas 2/6: Creare directoare pentru date..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "data\pdf" | Out-Null
New-Item -ItemType Directory -Force -Path "data\txt" | Out-Null
New-Item -ItemType Directory -Force -Path "data\enriched" | Out-Null
New-Item -ItemType Directory -Force -Path "data\dwh" | Out-Null
"[]" | Out-File -FilePath "data\enriched\cases.json" -Encoding UTF8
Write-Host "✅ Directoare create" -ForegroundColor Green

# Pas 4: Pornește Zookeeper
Write-Host ""
Write-Host "🐘 Pas 3/6: Pornire Zookeeper..." -ForegroundColor Yellow
docker compose up -d zookeeper
Write-Host "⏳ Așteptare Zookeeper să pornească (15 secunde)..." -ForegroundColor Cyan
Start-Sleep -Seconds 15
Write-Host "✅ Zookeeper pornit" -ForegroundColor Green

# Pas 5: Pornește Kafka
Write-Host ""
Write-Host "📨 Pas 4/6: Pornire Kafka..." -ForegroundColor Yellow
docker compose up -d kafka
Write-Host "⏳ Așteptare Kafka să pornească (20 secunde)..." -ForegroundColor Cyan
Start-Sleep -Seconds 20

# Verifică dacă Kafka a pornit
Write-Host "🔍 Verificare Kafka..." -ForegroundColor Cyan
$kafkaLogs = docker compose logs kafka 2>$null | Select-String "started"
if ($kafkaLogs) {
    Write-Host "✅ Kafka pornit cu succes!" -ForegroundColor Green
} else {
    Write-Host "⚠️  Kafka s-ar putea să nu fie complet pornit. Verifică logurile:" -ForegroundColor Yellow
    Write-Host "   docker compose logs kafka" -ForegroundColor Gray
}

# Pas 6: Pornește restul serviciilor
Write-Host ""
Write-Host "🔧 Pas 5/6: Pornire servicii de procesare..." -ForegroundColor Yellow
docker compose up -d
Write-Host "⏳ Așteptare servicii să pornească (10 secunde)..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Pas 7: Verifică starea serviciilor
Write-Host ""
Write-Host "📊 Pas 6/6: Verificare stare servicii..." -ForegroundColor Yellow
docker compose ps

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✅ Sistem pornit!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Accesează UI-ul la: http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "🔍 Verifică logurile:" -ForegroundColor Yellow
Write-Host "   docker compose logs -f ms_storage" -ForegroundColor Gray
Write-Host "   docker compose logs -f ms_pdftext" -ForegroundColor Gray
Write-Host ""
Write-Host "⚠️  Dacă vezi 'Connection refused', Kafka nu a pornit corect." -ForegroundColor Yellow
Write-Host "   Rulează: docker compose logs kafka" -ForegroundColor Gray
Write-Host ""
