import {Fragment,useEffect,useRef} from "react"
import {refs} from "$/utils/state"
import {Bare_comp_ca3d43ab446b1497222caba59bfe6248_72cd623b,Input_input_5be4018169cc2c2391b34b5a66fecbba_72cd623b} from "$/app_components/minrepro/minrepro"
import {jsx} from "@emotion/react"





function Component() {
const ref_title = useRef(null); refs["ref_title"] = ref_title;
const ref_g_out = useRef(null); refs["ref_g_out"] = ref_g_out;
const ref_g_page = useRef(null); refs["ref_g_page"] = ref_g_page;




  return (
    jsx(Fragment,{},jsx("div",{id:"g-page",ref:ref_g_page},jsx("h1",{id:"title",ref:ref_title},"G"),jsx(Input_input_5be4018169cc2c2391b34b5a66fecbba_72cd623b,{},),jsx("span",{id:"g-out",ref:ref_g_out},jsx(Bare_comp_ca3d43ab446b1497222caba59bfe6248_72cd623b,{},))),jsx("title",{},"Minrepro | G"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}
Component.displayName = "Component(g)";

export default Component;
