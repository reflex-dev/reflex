import {Fragment,useCallback,useContext,useEffect,useId,useRef,useState} from "react"
import {ReflexEvent,refs} from "$/utils/state"
import {EventLoopContext} from "$/utils/context"
import {jsx} from "@emotion/react"




function Input_843a68969daf114fd3ca0e6d78e2ebf0 () {
  const ref_g_in = useRef(null); refs["ref_g_in"] = ref_g_in;
const [addEvents, connectErrors] = useContext(EventLoopContext);

const on_change_56cf43522cf49f5fa68901feb7f8695f = useCallback(((_e) => (setCs_g(_e?.["target"]?.["value"]))), [addEvents, ReflexEvent])

  return (
    jsx("input",{id:"g-in",onChange:on_change_56cf43522cf49f5fa68901feb7f8695f,ref:ref_g_in},)
  )
}


function Span_3787b327c65372ff49498694f02e6b0a () {
  const ref_g_out = useRef(null); refs["ref_g_out"] = ref_g_out;
const id_zbxordmc = useId()
const [cs_g, setCs_g] = useState("")



  return (
    jsx("span",{id:"g-out",ref:ref_g_out},cs_g)
  )
}


export default function Component() {
const ref_g_page = useRef(null); refs["ref_g_page"] = ref_g_page;
const ref_title = useRef(null); refs["ref_title"] = ref_title;




  return (
    jsx(Fragment,{},jsx("div",{id:"g-page",ref:ref_g_page},jsx("h1",{id:"title",ref:ref_title},"G"),jsx(Input_843a68969daf114fd3ca0e6d78e2ebf0,{},),jsx(Span_3787b327c65372ff49498694f02e6b0a,{},)),jsx("title",{},"Minrepro | G"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}