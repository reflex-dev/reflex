import {Fragment,useCallback,useContext,useEffect,useId,useRef,useState} from "react"
import {ReflexEvent,refs} from "$/utils/state"
import {EventLoopContext} from "$/utils/context"
import {jsx} from "@emotion/react"




function Span_1c42f332c64de738089fc4ced6c38760 () {
  const ref_b_out = useRef(null); refs["ref_b_out"] = ref_b_out;
const id_xdvxrcsn = useId()
const [cs_b, setCs_b] = useState("b0")



  return (
    jsx("span",{id:"b-out",ref:ref_b_out},cs_b)
  )
}


function Button_623a0a76e14f0477088310576db013eb () {
  const ref_b_btn = useRef(null); refs["ref_b_btn"] = ref_b_btn;
const [addEvents, connectErrors] = useContext(EventLoopContext);

const on_click_5e6a9fde6aee917d9257d27e5ec6f1fa = useCallback((() => (setCs_b("b-clicked"))), [addEvents, ReflexEvent])

  return (
    jsx("button",{id:"b-btn",onClick:on_click_5e6a9fde6aee917d9257d27e5ec6f1fa,ref:ref_b_btn},"set-b")
  )
}


export default function Component() {
const ref_b_page = useRef(null); refs["ref_b_page"] = ref_b_page;
const ref_title = useRef(null); refs["ref_title"] = ref_title;




  return (
    jsx(Fragment,{},jsx("div",{id:"b-page",ref:ref_b_page},jsx("h1",{id:"title",ref:ref_title},"B"),jsx(Span_1c42f332c64de738089fc4ced6c38760,{},),jsx(Button_623a0a76e14f0477088310576db013eb,{},)),jsx("title",{},"Minrepro | B"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}