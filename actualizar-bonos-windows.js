#!/usr/bin/env node
/**
 * Actualizar Bonos desde IOL API (Windows - Node v24+)
 * 
 * Uso:
 *   node actualizar-bonos.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

// Cargar variables de entorno desde .env
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const IOL_USER = process.env.IOL_USER;
const IOL_PASS = process.env.IOL_PASS;
const REPO_PATH = process.env.REPO_PATH || '.';

if (!IOL_USER || !IOL_PASS) {
  console.error('❌ Error: Faltan credenciales en .env (IOL_USER, IOL_PASS)');
  process.exit(1);
}

// ──────────────────────────────────────────────────────────
// IOL AUTH
// ──────────────────────────────────────────────────────────

class IOLAuth {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = null;
  }

  async login(username, password) {
    const body = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}&grant_type=password`;

    const res = await fetch('https://api.invertironline.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body
    });

    if (!res.ok) {
      throw new Error(`IOL login fallido: ${res.statusText}`);
    }

    const data = await res.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.expiresAt = Date.now() + (data.expires_in * 1000);

    console.log('✓ Autenticado en IOL');
    return true;
  }

  async refresh() {
    const body = `refresh_token=${encodeURIComponent(this.refreshToken)}&grant_type=refresh_token`;

    const res = await fetch('https://api.invertironline.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body
    });

    if (!res.ok) {
      throw new Error('IOL refresh fallido');
    }

    const data = await res.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.expiresAt = Date.now() + (data.expires_in * 1000);

    return true;
  }

  isExpired() {
    return Date.now() >= this.expiresAt - 30000;
  }

  getAuthHeader() {
    return `Bearer ${this.accessToken}`;
  }
}

// ──────────────────────────────────────────────────────────
// FETCH CON AUTENTICACIÓN
// ──────────────────────────────────────────────────────────

async function fetchIOL(endpoint, auth) {
  if (auth.isExpired()) {
    await auth.refresh();
  }

  const res = await fetch(`https://api.invertironline.com${endpoint}`, {
    method: 'GET',
    headers: {
      'Authorization': auth.getAuthHeader()
    }
  });

  if (res.status === 401) {
    await auth.refresh();
    return fetchIOL(endpoint, auth);
  }

  if (!res.ok) {
    throw new Error(`IOL API error: ${res.statusText}`);
  }

  return res.json();
}

// ──────────────────────────────────────────────────────────
// MAIN
// ──────────────────────────────────────────────────────────

async function main() {
  try {
    console.log(`\n📊 Actualizando bonos... [${new Date().toLocaleString('es-AR')}]`);

    // 1. Autenticar
    const auth = new IOLAuth();
    await auth.login(IOL_USER, IOL_PASS);

    // 2. Traer instrumentos
    console.log('⟳ Descargando Letras (LECAPs/BONCAPs) desde IOL...');
    const letrasRaw = await fetchIOL('/api/v2/Cotizaciones/Letras/argentina/Todos', auth);
    const letrasArray = letrasRaw.titulos || [];

    console.log('⟳ Descargando Bonos Tasa Fija desde IOL...');
    const bonosTFRaw = await fetchIOL('/api/v2/Cotizaciones/Bonos/Soberanos%20en%20pesos%20a%20tasa%20fija/argentina', auth);
    const bonosTFArray = bonosTFRaw.titulos || [];

    // Combinar y eliminar duplicados
    const mapaUnificado = new Map();
    [...letrasArray, ...bonosTFArray].forEach(b => {
      if (b.simbolo) mapaUnificado.set(b.simbolo, b);
    });
    let bonosArray = Array.from(mapaUnificado.values());

    console.log(`✓ Procesando ${bonosArray.length} instrumentos (${letrasArray.length} letras + ${bonosTFArray.length} bonos TF)`);

    // 3. Transformar datos
    const bonos = bonosArray.map((b, idx) => {
      const vto = b.fechaVencimiento ? new Date(b.fechaVencimiento) : new Date(Date.now() + 365 * 24 * 60 * 60 * 1000);
      const hoy = new Date();
      const dias = Math.floor((vto - hoy) / (1000 * 60 * 60 * 24));
      const ticker = b.simbolo || 'N/A';
      const desc = (b.descripcion || '').toUpperCase();

      // Clasificar tipo
      let tipo = 'BONO';
      if (ticker.startsWith('S') && ticker.match(/S\d+[A-Z]\d+/)) tipo = 'LECAP';
      else if (ticker.startsWith('T') && ticker.match(/T\d+[A-Z]\d+/)) tipo = 'BONCAP';
      else if (ticker.startsWith('X')) tipo = 'XLETRA_CER';
      else if (desc.includes('CAPITALIZABLE') || desc.includes('CAP ')) tipo = 'LECAP';

      return {
        id: idx,
        ticker,
        descripcion: b.descripcion || '',
        tipo,
        // Normalizar precio: IOL Letras devuelve por 100VN (ej: 110.06)
        // El dashboard usa precio unitario (ej: 1.1006)
        const precioRaw = b.ultimoPrecio || b.puntas?.precioVenta || 0;
        const precioNorm = precioRaw > 10 ? precioRaw / 100 : precioRaw;
        precio: precioNorm,
        valVto: 100,
        diasCorr: 0,
        vtoSort: vto.toISOString().split('T')[0],
        dias: Math.max(dias, 1),
        vto: vto.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' }),
        volumen: parseFloat(b.volumen || 0),
        variacion: parseFloat(b.variacionPorcentual || 0),
        estado: 'data_viva',
        precioCompra: b.puntas?.precioCompra || 0,
        precioVenta: b.puntas?.precioVenta || 0,
        apertura: parseFloat(b.apertura || 0),
        minimo: parseFloat(b.minimo || 0),
        maximo: parseFloat(b.maximo || 0),
        mercado: b.mercado || 'BCBA',
        moneda: b.moneda || 'ARS$'
      };
    });

    console.log(`✓ ${bonos.length} bonos descargados`);

    // 4. Guardar JSON
    const outputData = {
      fecha_actualizacion: new Date().toISOString(),
      fuente: 'IOL_API_LIVE',
      horario_mercado: '10:30 - 17:00 ART',
      bonos: bonos,
      _meta: {
        script: 'actualizar-bonos.js',
        version: '1.0.0'
      }
    };

    const outputPath = path.join(REPO_PATH, 'data', 'bonos_live.json');
    const outputDir = path.dirname(outputPath);

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    fs.writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
    console.log(`✓ Guardado en: ${outputPath}`);

    console.log('✅ Completado\n');
    process.exit(0);

  } catch (e) {
    console.error('\n❌ Error:', e.message);
    process.exit(1);
  }
}

main();
