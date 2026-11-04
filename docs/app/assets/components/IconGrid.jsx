// Lucide's single-file build: the ESM entry shares per-icon modules with the
// chunks DynamicIcon creates, which would turn this import into ~1,700 requests.
import * as Lucide from "lucide-react/dist/cjs/lucide-react.js";

// Lucide's own kebab-case -> PascalCase rule (e.g. "grid-2x2-check" -> "Grid2x2Check").
const toPascal = (name) =>
  name.replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase());

export default function IconGrid({
  names,
  query,
  onCopy,
  gridClassName,
  tileClassName,
}) {
  return (
    <div className={gridClassName}>
      {names.map(([name, kebab]) => {
        const Icon = Lucide[toPascal(kebab)];
        if (!Icon || !name.startsWith(query)) return null;
        return (
          <div
            key={name}
            title={name}
            className={tileClassName}
            onClick={() => onCopy(name)}
          >
            <Icon />
          </div>
        );
      })}
    </div>
  );
}
