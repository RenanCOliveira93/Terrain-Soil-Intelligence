export const fmt = (v: number | null | undefined, digits = 1, unit = ""): string =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : `${v.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}${unit}`;

/** Intervalo de predição como texto: "37,8 [5,8–79,9]". */
export const fmtInterval = (m?: number, lo?: number, hi?: number, digits = 1): string =>
  m === undefined || lo === undefined || hi === undefined ? "–" : `${fmt(m, digits)} [${fmt(lo, digits)}–${fmt(hi, digits)}]`;

export const zoneLabel = (k: string): string => (k === "property" ? "Propriedade" : k);

/** Cor de texto legível (preto/branco) sobre um fundo hexadecimal. */
export const textOn = (hex: string): string => {
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? "#111" : "#fff";
};

export const bboxToBounds = (b: number[]): [[number, number], [number, number]] => [[b[0], b[1]], [b[2], b[3]]];

/** Coordenadas do quadrilátero de uma imagem no MapLibre: NO, NE, SE, SO. */
export const imageCoords = (b: number[]): [[number, number], [number, number], [number, number], [number, number]] =>
  [[b[0], b[3]], [b[2], b[3]], [b[2], b[1]], [b[0], b[1]]];
