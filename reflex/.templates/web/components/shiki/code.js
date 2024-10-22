import { useEffect, useState } from "react"
import { codeToHtml} from "shiki"

export function Code ({code, theme, language, transformers, ...divProps}) {
    const [codeResult, setCodeResult] = useState("")
    useEffect(() => {
        async function fetchCode() {
          let final_code;

          if (Array.isArray(code)) {
            final_code = code[0];
          } else {
            final_code = code;
          }
          const result = await codeToHtml(final_code, {
            lang: language,
            theme,
            transformers
          });
          setCodeResult(result);
        }
        fetchCode();
      }, [code, language, theme, transformers]

    )
    return (
        <div dangerouslySetInnerHTML={{__html: codeResult}} {...divProps}  ></div>
    )
}
