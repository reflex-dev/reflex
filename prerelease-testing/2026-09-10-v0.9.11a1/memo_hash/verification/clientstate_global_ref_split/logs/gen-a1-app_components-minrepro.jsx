
import {ReflexEvent,applyEventActions,isNotNullOrUndefined,isTrue,refs} from "$/utils/state"
import {jsx} from "@emotion/react"
import {Fragment,memo,useCallback,useEffect,useId,useRef,useState} from "react"
import {addEvents} from "$/utils/context"








export const Card_72cd623b = memo(({value:valueRxMemo, tid:tidRxMemo}) => {
    



    return(
        jsx("span",{className:"card",id:tidRxMemo},valueRxMemo)
    )
});
Card_72cd623b.displayName = "Card";

export const CardAndButton_72cd623b = memo(({tid:tidRxMemo, bid:bidRxMemo}) => {
    const id_wnkiegyk = useId()
const [cs_e, setCs_e] = useState("e0")



    return(
        jsx("div",{},jsx("span",{id:tidRxMemo},cs_e),jsx("button",{id:bidRxMemo,onClick:((_e) => (((...args) => ((() => (setCs_e("e-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e)))},"set-e"))
    )
});
CardAndButton_72cd623b.displayName = "CardAndButton";

export const Memocomponent_card_72cd623b_card_72cd623b_fd6b33c0f703a9811f24ec1943b89b9b_72cd623b = memo(({children}) => {
    const id_udaxihhe = useId()
const [cs_a, setCs_a] = useState("a0")



    return(
        jsx(Card_72cd623b,{tid:"a-out",value:cs_a},)
    )
});
Memocomponent_card_72cd623b_card_72cd623b_fd6b33c0f703a9811f24ec1943b89b9b_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_3eb7a18dc7ce188f10d0588df2a3e283_72cd623b = memo(({children}) => {
    const ref_a_btn = useRef(null); refs["ref_a_btn"] = ref_a_btn;
const on_click_4762b935bc60eb4db5bb76b45fe8ac04 = useCallback(((_e) => (((...args) => ((() => (setCs_a("a-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"a-btn",onClick:on_click_4762b935bc60eb4db5bb76b45fe8ac04,ref:ref_a_btn},children)
    )
});
Button_button_3eb7a18dc7ce188f10d0588df2a3e283_72cd623b.displayName = "Button";

export const Bare_comp_7d275e293d95e6385505debb4c38b28c_72cd623b = memo(({children}) => {
    const id_xdvxrcsn = useId()
const [cs_b, setCs_b] = useState("b0")



    return(
        cs_b
    )
});
Bare_comp_7d275e293d95e6385505debb4c38b28c_72cd623b.displayName = "Bare";

export const Button_button_9c1ee497c3ba4ed2078d97d54f1b84f2_72cd623b = memo(({children}) => {
    const ref_b_btn = useRef(null); refs["ref_b_btn"] = ref_b_btn;
const on_click_91b36984e0101b02842f1753a1c6562e = useCallback(((_e) => (((...args) => ((() => (setCs_b("b-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"b-btn",onClick:on_click_91b36984e0101b02842f1753a1c6562e,ref:ref_b_btn},children)
    )
});
Button_button_9c1ee497c3ba4ed2078d97d54f1b84f2_72cd623b.displayName = "Button";

export const Bare_comp_12fa2da57cfd125d4e4a4bbf7eb62d9a_72cd623b = memo(({children}) => {
    const id_bacghqta = useId()
const [cs_c, setCs_c] = useState("c0")



    return(
        null
    )
});
Bare_comp_12fa2da57cfd125d4e4a4bbf7eb62d9a_72cd623b.displayName = "Bare";

export const Memocomponent_card_72cd623b_card_72cd623b_15ed07689617a41f01af74f686223844_72cd623b = memo(({children}) => {
    const id_bacghqta = useId()
const [cs_c, setCs_c] = useState("c0")



    return(
        jsx(Card_72cd623b,{tid:"c-out",value:cs_c},)
    )
});
Memocomponent_card_72cd623b_card_72cd623b_15ed07689617a41f01af74f686223844_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_8dd23382b3f7963e07e436fc1d865416_72cd623b = memo(({children}) => {
    const ref_c_btn = useRef(null); refs["ref_c_btn"] = ref_c_btn;
const on_click_8b464817de333fd5e42a501da808b4e7 = useCallback(((_e) => (((...args) => ((() => (setCs_c("c-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"c-btn",onClick:on_click_8b464817de333fd5e42a501da808b4e7,ref:ref_c_btn},children)
    )
});
Button_button_8dd23382b3f7963e07e436fc1d865416_72cd623b.displayName = "Button";

export const Memocomponent_card_72cd623b_card_72cd623b_7ba721d2dfc29176beb89ae8f5cbd44a_72cd623b = memo(({children}) => {
    const id_rgwuwrnh = useId()
const [cs_d, setCs_d] = useState("d0")
refs['_client_state_setCs_d'] = ((osizayzf) => (Array.prototype.forEach.call([...(Object.values(refs['_client_state_dict_setCs_d'])), ...[(value) => { refs['_client_state_cs_d'] = value; }]], ((setter) => (setter(osizayzf))))))
refs['_client_state_cs_d'] ??= cs_d
refs['_client_state_dict_cs_d'] ??= {}
refs['_client_state_dict_setCs_d'] ??= {}
refs['_client_state_dict_cs_d'][id_rgwuwrnh] = refs['_client_state_cs_d']
refs['_client_state_dict_setCs_d'][id_rgwuwrnh] = setCs_d



    return(
        jsx(Card_72cd623b,{tid:"d-out",value:refs['_client_state_dict_cs_d'][id_rgwuwrnh]},)
    )
});
Memocomponent_card_72cd623b_card_72cd623b_7ba721d2dfc29176beb89ae8f5cbd44a_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_c4b3ff94714808e140a4ca190907e27e_72cd623b = memo(({children}) => {
    const ref_d_btn = useRef(null); refs["ref_d_btn"] = ref_d_btn;
const on_click_a4a683fa42d615a7ba8ab7f2bc1b4667 = useCallback(((_e) => (((...args) => ((() => (refs['_client_state_setCs_d']("d-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"d-btn",onClick:on_click_a4a683fa42d615a7ba8ab7f2bc1b4667,ref:ref_d_btn},children)
    )
});
Button_button_c4b3ff94714808e140a4ca190907e27e_72cd623b.displayName = "Button";

export const Input_input_a17f996b6622e1d5c92f55e51cc1814b_72cd623b = memo(({children}) => {
    const ref_f_in = useRef(null); refs["ref_f_in"] = ref_f_in;
const on_change_c466d020a2a5aac04b40b86241821ec8 = useCallback(((_e) => (((_e) => (setCs_f(_e?.["target"]?.["value"])))(_e))), [addEvents, ReflexEvent])
const id_dcmdllti = useId()
const [cs_f, setCs_f] = useState("")



    return(
        jsx("input",{id:"f-in",onChange:on_change_c466d020a2a5aac04b40b86241821ec8,ref:ref_f_in,value:(isNotNullOrUndefined(cs_f) ? cs_f : "")},)
    )
});
Input_input_a17f996b6622e1d5c92f55e51cc1814b_72cd623b.displayName = "Input";

export const Input_input_5be4018169cc2c2391b34b5a66fecbba_72cd623b = memo(({children}) => {
    const ref_g_in = useRef(null); refs["ref_g_in"] = ref_g_in;
const on_change_69ea10bd7cbcf910f2f53239b96f3b1f = useCallback(((_e) => (((_e) => (setCs_g(_e?.["target"]?.["value"])))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("input",{id:"g-in",onChange:on_change_69ea10bd7cbcf910f2f53239b96f3b1f,ref:ref_g_in},)
    )
});
Input_input_5be4018169cc2c2391b34b5a66fecbba_72cd623b.displayName = "Input";

export const Bare_comp_ca3d43ab446b1497222caba59bfe6248_72cd623b = memo(({children}) => {
    const id_zbxordmc = useId()
const [cs_g, setCs_g] = useState("")



    return(
        cs_g
    )
});
Bare_comp_ca3d43ab446b1497222caba59bfe6248_72cd623b.displayName = "Bare";
