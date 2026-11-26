// Un-annotated destructured parameters, whose object types have no symbol.
export function setup({ id, color }, [first, second]) {
  return [id, color, first, second];
}

export function resize(size: number): number {
  return size;
}
