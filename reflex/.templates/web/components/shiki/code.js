import { useEffect, useState } from "react"
import { codeToHtml} from "shiki"

/**
 * Code component that uses Shiki to convert code to HTML and render it.
 *
 * @param code - The code to be highlighted.
 * @param theme - The theme to be used for highlighting.
 * @param language - The language of the code.
 * @param transformers - The transformers to be applied to the code.
 * @param decorations - The decorations to be applied to the code.
 * @param divProps - Additional properties to be passed to the div element.
 * @returns The rendered code block.
 */
export function Code ({code, theme, language, transformers, decorations, ...divProps}) {
    const [codeResult, setCodeResult] = useState("")
    useEffect(() => {
        async function fetchCode() {
          const result = await codeToHtml(code, {
            lang: language,
            theme,
            transformers,
            decorations
          });
          setCodeResult(result);
        }
        fetchCode();
      }, [code, language, theme, transformers, decorations]

    )
    return (
        <div dangerouslySetInnerHTML={{__html: codeResult}} {...divProps}  ></div>
    )
}
