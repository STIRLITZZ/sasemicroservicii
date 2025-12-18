# DIAGNOSTICARE PIPELINE - PAȘI DE URMAT

## Pasul 1: Verifică ce servicii rulează

```powershell
cd C:\Users\andro\PycharmProjects\DateJuridice\Services
docker compose ps
```

**Arată-mi output-ul!** - Toate serviciile trebuie să fie "Up"

---

## Pasul 2: Verifică logs Kafka

```powershell
docker compose logs kafka --tail=20
```

**Arată-mi dacă apar erori!**

---

## Pasul 3: Verifică logs ms_ingestion_web

```powershell
docker compose logs ms_ingestion_web --tail=30
```

**Arată-mi ce apare când apeși Start!**

---

## Pasul 4: Verifică logs ms_storage

```powershell
docker compose logs ms_storage --tail=30
```

**Trebuie să vezi mesaje de procesare!**

---

## Pasul 5: Verifică logs ms_pdftext

```powershell
docker compose logs ms_pdftext --tail=30
```

---

## SOLUȚIE RAPIDĂ - Dacă nimic nu merge:

### RESTART COMPLET:

```powershell
cd C:\Users\andro\PycharmProjects\DateJuridice\Services

# Oprește tot
docker compose down

# Pornește cu scripti de startup
.\start.ps1
```

**SAU dacă start.ps1 nu merge:**

```powershell
# Pornește manual în ordinea corectă
docker compose up -d zookeeper
timeout /t 15

docker compose up -d kafka
timeout /t 20

docker compose up -d
```

---

## După restart:

1. Refresh browser (F5)
2. Selectează interval: 17/12/2025 → 18/12/2025
3. Click "Start"
4. Așteaptă 2-3 minute
5. Click "Încarcă Date"

---

**RULEAZĂ PAȘII 1-5 ȘI ARATĂ-MI OUTPUT-URILE!**
