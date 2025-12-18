#!/bin/bash
# Script de pornire corectă a tuturor serviciilor
# Rulează cu: bash start.sh

echo "============================================"
echo "🚀 Pornire Microservicii Date Juridice"
echo "============================================"
echo ""

# Verifică dacă Docker este disponibil
if ! command -v docker &> /dev/null; then
    echo "❌ Docker nu este instalat sau nu este în PATH"
    exit 1
fi

# Pas 1: Oprește toate containerele vechi
echo "📛 Pas 1/6: Oprire containere vechi..."
docker compose down
sleep 2

# Pas 2: Curăță volume-urile vechi (opțional, dar recomandat)
read -p "❓ Ștergi datele vechi? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Ștergere volume-uri vechi..."
    docker compose down -v
    echo "✅ Volume-uri șterse"
fi

# Pas 3: Creează directoarele necesare
echo "📁 Pas 2/6: Creare directoare pentru date..."
mkdir -p data/pdf data/txt data/enriched data/dwh
echo "[]" > data/enriched/cases.json
echo "✅ Directoare create"

# Pas 4: Pornește Zookeeper
echo ""
echo "🐘 Pas 3/6: Pornire Zookeeper..."
docker compose up -d zookeeper
echo "⏳ Așteptare Zookeeper să pornească (15 secunde)..."
sleep 15
echo "✅ Zookeeper pornit"

# Pas 5: Pornește Kafka
echo ""
echo "📨 Pas 4/6: Pornire Kafka..."
docker compose up -d kafka
echo "⏳ Așteptare Kafka să pornească (20 secunde)..."
sleep 20

# Verifică dacă Kafka a pornit
echo "🔍 Verificare Kafka..."
if docker compose logs kafka 2>/dev/null | grep -q "started"; then
    echo "✅ Kafka pornit cu succes!"
else
    echo "⚠️  Kafka s-ar putea să nu fie complet pornit. Verifică logurile:"
    echo "   docker compose logs kafka"
fi

# Pas 6: Pornește restul serviciilor
echo ""
echo "🔧 Pas 5/6: Pornire servicii de procesare..."
docker compose up -d
echo "⏳ Așteptare servicii să pornească (10 secunde)..."
sleep 10

# Pas 7: Verifică starea serviciilor
echo ""
echo "📊 Pas 6/6: Verificare stare servicii..."
docker compose ps

echo ""
echo "============================================"
echo "✅ Sistem pornit!"
echo "============================================"
echo ""
echo "📍 Accesează UI-ul la: http://localhost:8080"
echo ""
echo "🔍 Verifică logurile:"
echo "   docker compose logs -f ms_storage"
echo "   docker compose logs -f ms_pdftext"
echo ""
echo "⚠️  Dacă vezi 'Connection refused', Kafka nu a pornit corect."
echo "   Rulează: docker compose logs kafka"
echo ""
