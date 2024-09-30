import { useEffect, useState } from "react"
import { codeToHtml} from "shiki"

export function Code ({code, theme, language, themes, transformers}) {
    const [codeResult, setCodeResult] = useState("")
    useEffect(() => {
        async function fetchCode() {
          const result = await codeToHtml(code, {
            lang: language || "plaintext",
            theme: theme || "nord",
            transformers: transformers || []
          });
          setCodeResult(result);
        }
        fetchCode();
      }, [code, language, theme, themes, transformers]

    )

    return (
        <div dangerouslySetInnerHTML={{__html: codeResult}}></div>
    )
}
