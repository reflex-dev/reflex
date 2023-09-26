import { useEffect } from 'react'
import { embed } from '@bokeh/bokehjs'

export default function BokehFigure({
    fig,
    id,
    ...props
  }) {
    useEffect(() => {
      for (const elem of document.getElementById(id).children) {
        elem.remove()
      }
      const timeout = setTimeout(() => embed.embed_item(fig, id), 0)
      return () => {
        clearTimeout(timeout)
      }
    }, [fig, id]);
    return (
      <div className="bk-root" id={id} {...props}></div>
    )
  }