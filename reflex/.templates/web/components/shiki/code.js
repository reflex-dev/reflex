import { useEffect, useState } from "react"
import { codeToHtml} from "shiki"

export function Code ({code, theme, language, transformers, ...divProps}) {
    const [codeResult, setCodeResult] = useState("")
    useEffect(() => {
        async function fetchCode() {
          const result = await codeToHtml(code, {
            lang: language,
            theme,
            transformers
          });
          setCodeResult(result);
        }
        fetchCode();
      }, [code, language, theme, transformers]

    )
    console.log(divProps)
    return (
        <div dangerouslySetInnerHTML={{__html: codeResult}} {...divProps}  ></div>
    )
}
