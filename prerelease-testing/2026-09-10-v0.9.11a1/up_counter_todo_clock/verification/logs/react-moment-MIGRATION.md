# Migration guide

This guide covers breaking changes when upgrading from **1.2.3** to **2.0.0**, which migrates the library to TypeScript and replaces the class-based `Moment` component with a functional component.

If your usage is limited to rendering `<Moment />` with documented props, you may not need to change anything. Code that uses global configuration (`Moment.settings.format`, etc.) or the static pooled timer API (`Moment.startPooledTimer()` / `Moment.clearPooledTimer()`) must move those defaults into a wrapping `<MomentProvider>`.

## Summary

| Area | 1.2.3 | 2.0.0 |
| --- | --- | --- |
| Component implementation | React class component | React function component (hooks) |
| Source language | JavaScript (`.jsx` / `.js`) | TypeScript (`.tsx` / `.ts`) |
| Runtime prop validation | PropTypes | None (TypeScript types only) |
| `prop-types` peer dependency | Required | Removed |
| Published entry point | `dist/index.js` | `dist/index.cjs.js` (main), `dist/index.mjs` (ESM), `dist/index.umd.js` (CDN) |
| Type declarations | Hand-written class typings | Generated from TypeScript source |

---

## Remove `prop-types` as a peer dependency

**1.2.3** listed `prop-types` as a peer dependency and validated props at runtime via `PropTypes`.

**2.0.0** removes runtime validation entirely. Type information is provided only through TypeScript declarations.

### What to change

- Remove `prop-types` from your dependencies if you installed it solely to satisfy `react-moment`'s peer dependency warning.
- Do not expect development-time console warnings from `react-moment` when invalid props are passed; rely on your own TypeScript checks or tests instead.

### Peer dependencies (2.0.0)

```json
{
  "peerDependencies": {
    "moment": "^2.29.0",
    "react": "^18.0.0 || ^19.0.0"
  }
}
```

---

## `Moment` is no longer a class component

In **1.2.3**, `Moment` extended `React.Component`. It is now a function component. Shared defaults that previously lived on `Moment.settings` are supplied with `<MomentProvider>`.

### Breaking if you relied on class-component internals

The following patterns **no longer work**:

```jsx
// instanceof checks
if (instance instanceof Moment) { /* ... */ }

// Instance methods on a mounted component
ref.current.update();
ref.current.setTimer();
ref.current.clearTimer();
ref.current.getTitle();
ref.current.componentWillUnmount();

// TestUtils helpers that expect a class instance
TestUtils.findRenderedComponentWithType(container, Moment);
```

### Global settings now use `MomentProvider`

The `Moment.settings` object has been removed. Move global defaults to a provider that wraps the `<Moment>` instances that should receive them:

```jsx
// 1.2.3
Moment.settings.locale = 'fr';
Moment.settings.format = 'D MMM YYYY';
Moment.settings.element = 'span';

// 2.0.0
<MomentProvider locale="fr" format="D MMM YYYY" element="span">
    <Moment>{date}</Moment>
</MomentProvider>
```

`<MomentProvider>` accepts the former settings fields as props: `moment`, `locale`, `local`, `format`, `parse`, `filters`, `renderers`, `element`, and `timezone`. Providers compose, so nested providers inherit parent defaults and override only the props they set.

Named utility exports are still available from `react-moment`: `getDatetime(props)`, `getContent(props)`, and `getShortRelativeTime(datetime)`.

Normal JSX usage is unchanged:

```jsx
<Moment fromNow>{date}</Moment>
<Moment format="YYYY-MM-DD" date={date} />
```

### Default prop behavior

**1.2.3** declared defaults via `static defaultProps` on the class. The functional component applies the same effective defaults through runtime fallbacks (for example, `interval ?? 60000`, no filters when none are provided, falsy boolean props treated as `false`). Typical usage does not need changes.

### `onChange` fires on mount

**2.0.0** invokes `onChange` once when `<Moment>` or `useMomentContent` mounts, with the initial formatted content, then again on each interval tick (including when registered with a pooled `<MomentProvider pool>` timer). This matches typical controlled-component expectations: you can sync external state immediately without waiting for the first timer.

- `interval={0}` disables periodic re-renders but still calls `onChange` on mount.
- The callback receives `MomentContent` (`string | number`), not a `Date` or moment object.

If you previously assumed `onChange` only ran after the first `interval` elapsed, initialize state from rendered output or accept the extra mount callback.

---

## Pooled timer configuration moved to `MomentProvider`

**1.2.3** enabled pooled timing with static methods and stored mounted `Moment` **class instances** in `Moment.pooledElements`.

**2.0.0** enables pooled timing per provider. Wrap the relevant subtree in `<MomentProvider pool>` and set the pooled interval with the provider's `interval` prop:

```jsx
// 1.2.3
Moment.startPooledTimer(30000);

// 2.0.0
<MomentProvider pool interval={30000}>
    <Moment fromNow>{date}</Moment>
</MomentProvider>
```

Provider-backed pools store lightweight **pool entries** instead of component instances:

```ts
interface PoolEntry {
  getProps: () => MomentProps;
  update: () => void;
}
```

### Breaking if you used static pooling APIs or accessed the pool directly

```jsx
// 1.2.3 — no longer valid
Moment.startPooledTimer();
Moment.clearPooledTimer();

Moment.pooledElements.forEach((instance) => {
  instance.update();
});

Moment.pushPooledElement(myMomentInstance);
```

### What to change

- Use `<MomentProvider pool>` instead of `Moment.startPooledTimer()` / `Moment.clearPooledTimer()`.
- If you inspected `pooledElements`, iterate entries and call `entry.update()` or read props via `entry.getProps()` instead of treating entries as component instances.

---

## Singular `filter` prop removed

The `filter` prop has been removed from `<Moment>` and `<MomentProvider>`. Use the `filters: Filter[]` array instead.

### What to change

```jsx
// 1.x / early 2.0 beta
<Moment filter={toUpper}>{date}</Moment>
<MomentProvider filter={toUpper}>...</MomentProvider>

// 2.0
<Moment filters={[toUpper]}>{date}</Moment>
<MomentProvider filters={[toUpper]}>...</MomentProvider>
```

For multiple transforms, pass them in order:

```jsx
<Moment filters={[trim, toUpper]}>{date}</Moment>
```

### Precedence change

In **1.x**, the provider's `filter` overrode a per-instance `filter` when both were set. In **2.0**, `filters` and `renderers` from a `<MomentProvider>` and a `<Moment>` are **merged**: provider entries run first, then per-instance entries.

For `filters`, all functions run in order (provider filters first, then instance filters). For `renderers`, the merged chain is tried in order; the first renderer to return a non-`undefined` value wins (still before built-in renderers).

Code that depended on provider-only transforms when both were set will now run both arrays. To restore the old behavior, move the desired transform entirely onto the instance (or provider) instead of splitting across both.

---

## TypeScript declaration changes

Type declarations are now generated from the TypeScript source (`tsc --emitDeclarationOnly`) rather than hand-maintained class typings.

### Component type

**1.2.3:**

```ts
declare class Moment extends Component<MomentProps, any> { /* ... */ }
export default Moment;
```

**2.0.0:**

```ts
declare const Moment: React.FC<MomentProps> & MomentStatics;
export default Moment;
```

Update code that types refs or variables as `Moment` (the class) or `Component<MomentProps>`.

### `MomentProps` changes

Notable differences:

| Prop / area | 1.2.3 | 2.0.0 |
| --- | --- | --- |
| `add` / `subtract` | `subtractOrAddTypes` (loose object) | `moment.DurationInputObject` |
| `date`, `from`, `to`, etc. | `dateTypes` (`string \| number \| array \| object`) | `moment.MomentInput` |
| `parse` | `string \| Array<any>` | `moment.MomentFormatSpecification` |
| `calendar` | `boolean \| object` | `boolean \| moment.CalendarSpec` |
| `unit` | `string` | `moment.unitOfTime.Diff` |
| `onChange` | `(content: any) => any`; fires on interval ticks | `(content: MomentContent) => void`; fires on mount and on each tick (see above) |
| `element` | `string \| FunctionComponent \| ComponentClass` | `ElementType \| null` |
| Passthrough DOM props | Explicit optional props (`className`, `style`, …) | Index signature `[key: string]: unknown` |

Stricter types may surface existing type errors in TypeScript projects. Adjust call sites or narrow types at boundaries as needed.

### New exported declaration files

The published package includes additional `.d.ts` files alongside `dist/index.d.ts`:

- `dist/types.d.ts` — `MomentProps`, `MomentStatics`, `PoolEntry`, and related types
- `dist/objects.d.ts` — `objectKeyFilter` utility
- `dist/utils.d.ts` — helper implementations (`getDatetime`, `getContent`, etc.); also re-exported from `dist/index.d.ts`

These are primarily for advanced use and type re-exports; the default import path remains `react-moment`.

### Removed static members in typings

**2.0.0** removes the public static members used for global settings and pooled timers. Replace them with `<MomentProvider>` props:

- `Moment.settings`
- `Moment.startPooledTimer(interval?)`
- `Moment.clearPooledTimer()`
- `Moment.pooledElements`
- `Moment.pooledTimer`
- `Moment.pushPooledElement(entry)`
- `Moment.removePooledElement(entry)`

Helper functions remain named exports from the package entry point:

```ts
import Moment, { getDatetime, getContent, getShortRelativeTime } from 'react-moment';
```

In React components, prefer `useMomentContent` instead of calling those helpers directly. It uses the same formatting pipeline as `<Moment>`, respects `<MomentProvider>` defaults, and returns `{ content, datetime, title? }` with automatic re-renders when dates change. The returned `datetime` is the same adjusted moment used to produce `content` (including `add`, `subtract`, `utc`, `local`, `tz`, and provider defaults), not the raw parsed input:

```ts
import { useMomentContent } from 'react-moment';

const { content, datetime } = useMomentContent({ fromNow: true, children: date });
```

For read-only access to provider settings, use `useMomentContext`.

---

## Source layout (monorepo / deep imports)

If you imported from source paths inside the package (unusual for npm consumers), file extensions and locations changed:

| 1.2.3 | 2.0.0 |
| --- | --- |
| `src/index.jsx` | `src/index.tsx` |
| `src/types.js` | `src/types.ts` |
| `src/objects.js` | `src/objects.ts` |
| — | `src/utils.ts` (new; date/content helpers) |

The supported public API remains the built artifacts (`dist/index.cjs.js`, `dist/index.mjs`, `dist/index.umd.js`) with types at `dist/index.d.ts`. Deep imports from `src/` are not part of the supported API.

---

## Non-breaking for typical consumers

The following continue to work without changes:

- All documented JSX props (`fromNow`, `format`, `unix`, `tz`, `fromNowShort`, etc.)
- UMD / CommonJS / AMD consumption via `require('react-moment')` or `import Moment from 'react-moment'`
- Default render output (still a `<time>` element unless overridden with the `element` prop or `<MomentProvider element="...">`)

---

## Upgrade checklist

1. Upgrade `react-moment` to the new version.
2. Remove `prop-types` if it is only present for this package's peer dependency.
3. Replace `Moment.settings` assignments with `<MomentProvider>` props.
4. Replace `Moment.startPooledTimer()` / `Moment.clearPooledTimer()` with `<MomentProvider pool>`.
5. Search your codebase for `instanceof Moment`, refs to `Moment` instance methods, or direct use of `Moment.pooledElements` / `Moment.pushPooledElement`.
6. If you use TypeScript, fix type errors from the updated `MomentProps` and function-component typing.
7. Replace `filter={fn}` (on `<Moment>` or `<MomentProvider>`) with `filters={[fn]}`.
8. Run your test suite; replace any tests that call `componentWillUnmount()` on a rendered `Moment` instance with a normal React unmount (`ReactDOM.unmountComponentAtNode(container)` or `@testing-library/react`'s `unmount()`).
