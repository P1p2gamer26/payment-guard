# Payment Guard — DESIGN.md (v2)

Base: **Mercury** de getdesign.md (https://getdesign.md/mercury/design-md) para el tono (banca confiable, calma, un solo acento) y **Linear** (https://getdesign.md/linear.app/design-md) para la densidad de lista/detalle. Solo se pudo leer el resumen público de cada marca, no el DESIGN.md completo; los tokens son propios.
Estructura de app inspirada en la referencia que compartió Julian (workspace con sidebar, biblioteca de 3 paneles con evidencia por campo). No se usa ni el nombre ni el logo de Blinka como producto: la marca es **Payment Guard**; el borrador se describe como "compatible con la API de Blinka".

## 1. Principios
1. **Decisión primero**: PAGAR / FRENAR / ESCALAR, la regla citada y el monto se leen en 2 s.
2. **El código decide, y se ve**: la regla que disparó es el centro del detalle; las posteriores quedan "no evaluadas".
3. **Cada dato tiene origen**: todo campo extraído apunta a la línea del documento original.
4. **Color = significado**: verde/rojo/ámbar solo para decisiones; el acento de marca solo para agente, foco y selección.
5. **Mono para datos, sans para voz**; el movimiento solo explica flujo o cambio de estado.

## 2. Paletas (3, conmutables en el prototipo con el selector de círculos)
Los tres tonos semánticos (PAGAR verde, FRENAR rojo, ESCALAR ámbar) se mantienen reconocibles en las tres; cambian el acento, los neutros y el segundo color de la "doble llave". Evitadas a propósito: navy+teal genérico, azul-morado, crema+terracota, negro+verde ácido.

| | **A · Cobalto** (recomendada, por defecto) | B · Ciruela | C · Latón |
|---|---|---|---|
| Acento claro / oscuro | `#1F55D0` / `#6B93FF` | `#7B2A68` / `#E08BCB` | `#8A6414` / `#D7A840` |
| Segundo (llave B) | `#7D8A99` / `#AEB8C4` plata | `#6B7A8F` / `#B8C0CC` | `#3C4A57` / `#9FB0BF` |
| Fondo claro / oscuro | `#EDEFF1` / `#0E1114` (gris piedra neutro frío) | `#F2EFF2` / `#130E14` | `#F0F0EE` / `#121211` |
| Superficie | `#FFFFFF` / `#161B20` | `#FFFFFF` / `#1C1520` | `#FFFFFF` / `#1A1A18` |
| Tinta | `#14181D` / `#ECEFF2` | `#1D1620` / `#F3EDF4` | `#1C1B17` / `#EEEDE8` |
| PAGAR | `#12784F` / `#44D69A` | `#15764C` / `#4BD99F` | `#1B7A4B` / `#4CD79B` |
| FRENAR | `#B8322C` / `#FF8179` | `#C03A2B` / `#FF8A78` | `#B3261E` / `#FF8A80` |
| ESCALAR | `#9A5A00` / `#FFC15A` | `#9A5A00` / `#FFC15A` | `#C2410C` / `#FF9A57` (naranja, para separarlo del latón) |

**Por qué Cobalto**: (1) es la única cuyo acento queda lejos de los tres semánticos (el ciruela roza el rojo en oscuro; el latón roza el ámbar y obliga a mover ESCALAR a naranja); (2) neutros fríos de gris piedra, sin tinte azul-marino, evitan el "fintech genérico navy"; (3) cobalto sobre blanco da 6,3:1 y sobre `#0E1114` el tono claro `#6B93FF` supera 6:1; (4) la segunda llave en plata mantiene la doble llave legible (dos llaves, un solo acento); (5) es sobria, confiable para finanzas y distinta del teal de la v1. Ciruela es la alternativa más distintiva; Latón la más "banca privada".
Tokens (nombres CSS): `--bg --surface --s2 --ink --ink-2 --line --ac --ac2 --acbg --onac --pay/--paybg/--onpay --stop/… --esc/… --stage --paper --focus --shadow`. Se activan con `<html data-palette="cobalto|ciruela|laton">` y `data-theme="light|dark"` (si falta, `prefers-color-scheme`). Se guardan en `localStorage` (con try/catch). La escena 3D lee estas variables y se recolorea sola.

## 3. Tipografía
**Geist** (UI, 400–700) y **Geist Mono** (ids, reglas, montos, JSON, etiquetas en mayúsculas con tracking). Escala: 10,5 / 11 / 12,5 / 14 (base) / 15 / 20 (h2) / 30 (h1) / 32 (KPI). Cifras con `tabular-nums`. Sin Inter ni serif.

## 4. Layout y componentes
- **App shell**: sidebar 248 px (marca, workspace "Lumbre Analytics, Inc." ficticio, navegación: Centro de decisiones · Biblioteca de facturas · Aprobaciones · Reglas y parámetros · Registro; ciclo activo Octubre 2026 · Abierto); topbar con breadcrumbs, política vigente, selector de paleta y tema. En <1060 px la sidebar pasa a barra superior con navegación desplazable.
- **Centro de decisiones**: escena 3D + línea "procesando #N → regla → decisión" sincronizada, 5 pasos, 4 KPIs (autonomía 56 %, pagos indebidos 0, presupuesto restante, doble lectura 20/25) y 3 carriles con las 25 facturas.
- **Biblioteca**: KPIs, búsqueda, filtros (estado, formato), chips de rutas de recepción con conteos (Correo 7, Portal 11, API 3, WhatsApp 2, Slack 1, Telegram 1: rutas de ejemplo) y 3 paneles: lista · documento original con líneas numeradas y campo resaltado · pasos 1 Documento, 2 Extracción (con evidencia "Origen: «…» · línea N"), 3 Doble llave (LLM vs regex, abstención), 4 Reglas (ruta de 13 + gauge valor-vs-límite), 5 Decisión (ticket con sello). Clic en un campo ilumina el original y viceversa.
- **Aprobaciones**: tarjeta por escalada con re-chequeo visible (beneficiario registrado / límite / presupuesto), nota obligatoria, Aprobar / Rechazar, y borrador JSON compatible con la API de Blinka (`draft_not_executed`, cuenta del registro maestro).
- **Reglas y parámetros**: editor de límite, umbral y presupuesto; "Aplicar" crea una versión y lista qué decisiones cambian; tabla de las 13 reglas con conteo de facturas.
- **Registro**: eventos con política y hash encadenado; filtro y descarga CSV.
- **Sello**: mono 700, borde 2 px del color de la decisión, rotado -3°; único elemento inclinado. **Radios**: 2 px datos/chips/sellos, 6 px tarjetas, 10 px contenedores. Un solo sombreado de tarjeta.

## 5. Escena 3D (`flow3d.js`, `mountFlow(el,{reducedMotion,items,onItem})`)
Recorre las 25 facturas reales en bucle. Cada formato tiene su forma: sobre (correo), burbuja (chat), hoja con esquina doblada (cuenta de cobro / factura) y hoja CFDI. Al llegar al nodo "LLM extrae" los campos saltan del documento al icosaedro y vuelven como barras de datos. "Doble llave": dos llaves giran y encajan en la cerradura si el regex leyó (la cerradura se vuelve verde); si el regex se abstiene, la llave B queda a medias (ámbar). "Motor": túnel de 13 anillos etiquetados que se encienden en orden hasta la regla que dispara (con el color de la decisión). Luego tres carriles: PAGAR a su bandeja, FRENAR contra una barrera, ESCALAR a una persona que re-chequea (check verde y borrador `draft_not_executed` para la 25; cruz roja para las bloqueadas). La 24 lleva campos ámbar y etiqueta "R_SOSPECHA · inyección". Rastro de partículas sobrio (140 puntos), cámara con leve vaivén, etiquetas con sprites. Sin postprocesado; pausa fuera de pantalla; píxel ratio ≤ 2. Aspecto vertical (móvil): el mundo gira 90° y el flujo corre de arriba abajo. Reduced-motion o sin WebGL: diagrama SVG estático.

## 6. Movimiento y accesibilidad
Duraciones 140 / 260 / 420 ms, easing `cubic-bezier(.2,.7,.2,1)`; sello rotado que cae; regla disparada con halo 1,8 s. `prefers-reduced-motion` anula animaciones CSS y sustituye la escena. Foco visible 2 px; estados con texto además de color; campos resaltados accesibles por teclado (Enter); contraste AA; sin scroll horizontal a 400 px.

## 7. No hacer
- Usar el logo o nombre de Blinka como si fuera el producto.
- Crema + serif + terracota, gradiente morado, Inter por defecto, emojis, todo centrado, `rounded-lg` en todo, glassmorphism, neón.
- Verde para algo que no sea PAGAR; botones rojos para "Rechazar"; mostrar la cuenta de la factura como destino del pago.
- Animar sin explicar flujo; sugerir que el borrador mueve dinero.
- `|safe` / `mark_safe` con datos de facturas (el prototipo escapa todo con `esc()`).
