# Payment Guard — DESIGN.md

Base elegida: **Mercury** de getdesign.md (https://getdesign.md/mercury/design-md), con tomas de **Linear** (https://getdesign.md/linear.app/design-md) para la bandeja y el detalle.
Nota de fuente: de getdesign.md solo se pudo leer el resumen público de cada marca (Mercury: "un banco privado hecho software", base oscura tinta-violeta con transición a claro, un único acento de acción, tipografía sans a pesos ligeros; Linear: ultra-minimal, preciso, un acento). El DESIGN.md completo requiere descargar el archivo (`npx getdesign@latest add mercury`); no se hizo. Los tokens de abajo son nuestros, adaptados a la marca Blinka (navy `#04243C`, teal `#2B9CAE`).

**Por qué Mercury**: es el referente de banca confiable y moderna: calma, un solo acento, oscuro-a-claro. Cambiamos el violeta por el navy/teal de Blinka y añadimos tres colores semánticos (PAGAR, FRENAR, ESCALAR) como únicos colores "ruidosos".

## 1. Principios
1. **Decisión primero.** Lo que importa (PAGAR/FRENAR/ESCALAR, regla citada, monto) se lee en 2 s. Todo lo demás es secundario.
2. **El código decide, y se ve.** La regla que disparó es el elemento visual principal del detalle; las posteriores se atenúan ("no evaluada").
3. **Color = significado.** Verde/rojo/ámbar solo para decisiones. Teal solo para "agente / flujo". Nada decorativo.
4. **Mono para datos, sans para voz.** Montos, reglas, cuentas, ids en mono tabular.
5. **Movimiento que explica.** Solo se anima flujo, estado o cambio de decisión.

## 2. Color (tokens)
| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--bg` | `#F3F6F8` | `#04141F` | fondo de página |
| `--surface` | `#FFFFFF` | `#0A2132` | tarjetas |
| `--surface-2` | `#E9EFF3` | `#0F2D43` | hover, pistas, selección |
| `--ink` | `#04243C` | `#E8F2F7` | texto |
| `--ink-2` | `#3F5C70` | `#9DBBCB` | texto secundario (AA sobre `--surface`) |
| `--line` | `#D1DEE6` | `#1B3B53` | bordes |
| `--teal` | `#177487` | `#4CC3D6` | agente, flujo, enlaces (en 3D: `#2B9CAE`) |
| `--blue` | `#2350A9` | `#7FA3FF` | segunda llave, foco |
| `--pay` / `--pay-bg` | `#137A52` / `#E1F4EA` | `#3DD9A0` / `#0B3326` | PAGAR |
| `--stop` / `--stop-bg` | `#BE2F3A` / `#FBE7E9` | `#FF7B80` / `#3A1519` | FRENAR |
| `--esc` / `--esc-bg` | `#955700` / `#FCEFD6` | `#FFC15A` / `#3A2A0A` | ESCALAR |
Estados nunca solo por color: siempre texto (sello, etiqueta de regla) además del color.
Modo: sigue `prefers-color-scheme`; `data-theme="light|dark"` en `<html>` lo fuerza; se recuerda en `localStorage` (con try/catch).

## 3. Tipografía (Google Fonts)
- **Geist** 400/500/600/700: UI y titulares (tracking -0.025 a -0.035em en titulares).
- **Geist Mono** 400/500/600: ids, reglas, montos, JSON, etiquetas pequeñas en mayúsculas (tracking +0.06 a 0.14em).
- Escala: 11 / 12 / 13 / 15 (base) / 17 (lede) / 22 / 28 (h2) / 36 (monto) / 40 (métrica) / clamp(32–58) (h1). Cifras con `tabular-nums`.
- Prohibido Inter como fuente por defecto, y serif editorial.

## 4. Espaciado, radios, sombras
- Espaciado base 4 px; pasos 4, 8, 12, 16, 20, 24, 32, 56. Contenedor 1240 px, gutter 24 (16 en móvil).
- Radios con jerarquía: `--r0` 2 px (datos: tickets, chips, inputs, sellos), `--r1` 6 px (tarjetas, carriles), `--r2` 10 px (contenedores grandes: escena, métricas). Círculo solo en puntos de ruta.
- Sombra única de tarjeta: `0 1px 0 rgba(4,36,60,.04), 0 8px 24px -12px rgba(4,36,60,.18)` (oscuro: negra más profunda). Sin glows en UI; el brillo es del 3D.

## 5. Movimiento
- Duraciones: `--t-fast` 140 ms (hover), `--t-med` 260 ms (estado), 420 ms sello, 800–900 ms barras que crecen. Easing: `cubic-bezier(.2,.7,.2,1)`.
- Sello: aparece rotado -9° y escala 1.5 → -3° en 420 ms. Regla disparada: pulso suave 1.8 s en bucle.
- Escena 3D: bucle de 10 facturas, 2,5 u/s, una cada ~1,5 s; se pausa fuera de pantalla (IntersectionObserver) y en pestaña oculta; sin postprocesado; píxel ratio máx. 2.
- `prefers-reduced-motion: reduce`: se desactivan animaciones/transiciones CSS y la escena 3D se sustituye por un diagrama SVG estático. Sin WebGL: mismo fallback.

## 6. Componentes
- **Ticket de decisión**: borde de 1 px, `--r0`, cabecera con id + formato en mono, nombre 22/600, monto 36 mono, sello a la derecha, párrafo "por qué" con chip de regla, gauge, dl de claves (beneficiario, cuenta del registro, presupuesto).
- **Sello**: texto mono 700 en mayúsculas, borde 2 px del color de la decisión, rotado -3°. Es el único elemento inclinado.
- **Ruta de reglas**: lista vertical de las 13 reglas en orden con línea conectora: `pasó` (punto teal con check), `dispara` (punto del color de la decisión con halo pulsante, texto en negrita), `no evaluada` (opacidad .45). Una fila por regla con código mono y descripción corta.
- **Gauge valor-vs-límite**: pista 0–8.000 USD; relleno del color de la decisión; marcas verticales en 3.000 (umbral de aprobación) y 6.000 (límite duro); texto con el exceso ("+USD 1.000 sobre el límite").
- **Tablero**: 3 carriles con borde superior de 3 px del color; conteo grande; tickets compactos (id, beneficiario, monto, regla). El seleccionado lleva barra lateral de 3 px. En <980 px los carriles pasan a pestañas.
- **Bandeja de aprobación**: tarjeta con borde izquierdo ámbar; nota obligatoria; Aprobar (primario) / Rechazar (fantasma); mensajes de error mono en rojo ("presupuesto insuficiente; restan USD …"). Tras decidir: borde verde/rojo y estado fijo.
- **Borrador Blinka**: bloque navy fijo (igual en claro/oscuro) con JSON coloreado (claves teal, cadenas verde, números ámbar) y sello `DRAFT · NOT EXECUTED`. Siempre se muestra la cuenta del registro maestro, nunca la de la factura.
- **Métrica**: etiqueta mono mayúsculas, valor 40/600, subtexto; "0 pagos indebidos" en verde. Cuatro: autonomía 56 % (14/25), pagos indebidos 0, presupuesto restante (USD 2.483 de 40.000, baja al aprobar), doble lectura 20/25.

## 7. Escena 3D (hero)
Flujo de izquierda a derecha sobre una cinta: Facturas (tarjetas con etiqueta CORREO/CFDI/CHAT/COBRO) → anillo + icosaedro "LLM extrae" (aparecen campos en la tarjeta) → dos anillos "Doble llave" → caja "Motor de reglas" con 13 barras que se encienden en orden hasta la regla que dispara → tres carriles. PAGAR cae a su bandeja; FRENAR choca contra una barrera roja; ESCALAR llega a una persona y, si se aprueba, sale una hoja `draft_not_executed`. La factura 24 (inyección) lleva campos ámbar, dispara `R_SOSPECHA · inyección` en la barra 1 y se desvía a ESCALAR (la persona la deja sin borrador). Tema claro/oscuro reactivo. API: `mountFlow(el, {reducedMotion})` devuelve `{destroy()}` o `null` (usar fallback).

## 8. Accesibilidad y responsive
- Foco visible: 2 px `--focus` con offset 2. Contraste AA en texto; estados con texto además de color.
- Escena `role="img"` con descripción; canvas `aria-hidden`.
- Sin scroll horizontal a 400 px; 5 pasos y métricas colapsan a 2 y 1 columnas.

## 9. No hacer
- Crema + serif + terracota, gradiente morado, Inter por defecto, emojis, todo centrado, `rounded-lg` en todo.
- Glassmorphism, neón en la UI, sombras de colores, bordes con gradiente, tarjetas idénticas de tres iconos.
- Color de decisión como adorno; verde para algo que no sea PAGAR; botones de rojo para "Rechazar" (se usa fantasma).
- Animar sin explicar flujo; loops rápidos; parpadeos; autoplay con sonido.
- Mostrar la cuenta bancaria de la factura como destino; sugerir que el borrador mueve dinero.
- `|safe` o `mark_safe` con datos de facturas (en el prototipo, datos externos entran con `textContent`).
