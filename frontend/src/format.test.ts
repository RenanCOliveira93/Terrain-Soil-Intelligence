import { describe, expect, it } from "vitest";
import { fmt, fmtInterval, imageCoords, textOn, zoneLabel } from "./format";

describe("format", () => {
  it("formata números no padrão pt-BR e trata ausentes", () => {
    expect(fmt(1234.567, 1)).toBe("1.234,6");
    expect(fmt(null)).toBe("–");
    expect(fmt(undefined, 2, " ha")).toBe("–");
    expect(fmt(Number.NaN)).toBe("–");
    expect(fmt(5.5, 0, "%")).toBe("6%");
  });
  it("mostra a média com o intervalo de 90%", () => {
    expect(fmtInterval(37.8, 5.8, 79.9)).toBe("37,8 [5,8–79,9]");
    expect(fmtInterval(undefined, 1, 2)).toBe("–");
  });
  it("rotula a zona da propriedade", () => {
    expect(zoneLabel("property")).toBe("Propriedade");
    expect(zoneLabel("Talhão A")).toBe("Talhão A");
  });
  it("escolhe texto legível", () => {
    expect(textOn("#ffffff")).toBe("#111");
    expect(textOn("#14532d")).toBe("#fff");
  });
  it("ordena o quadrilátero NO, NE, SE, SO", () => {
    expect(imageCoords([1, 2, 3, 4])).toEqual([[1, 4], [3, 4], [3, 2], [1, 2]]);
  });
});
