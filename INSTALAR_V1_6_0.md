# Instalar Disney Sentinel v1.6.0

1. Aplicar este PATCH sobre una instalación backend v1.5.6.
2. No reemplazar `config/`, `data/`, `reports/` ni secretos.
3. Ejecutar:

```bash
npm install --no-audit --no-fund
npm test
```

4. Publicar:

```bash
git add .github/workflows/monitor-availability.yml src/application/run-availability-all.ts src/cli.ts tests/unit/availability-batch.test.ts package.json package-lock.json CHANGELOG.md RELEASE_NOTES_V1_6_0.md INSTALAR_V1_6_0.md CONTENIDO_V1_6_0.txt MANIFEST_V1_6_0.json
git commit -m "Disney Sentinel v1.6.0 all date windows"
git push origin main
```

5. Esperar que el workflow `Test` finalice correctamente antes de instalar el Dashboard v3.2.0.
