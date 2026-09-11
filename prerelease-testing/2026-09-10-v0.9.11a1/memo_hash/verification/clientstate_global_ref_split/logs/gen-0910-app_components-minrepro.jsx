
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

export const Memocomponent_card_72cd623b_card_72cd623b_9ba0ddbe21efbd49351eafd7d03c73dd_72cd623b = memo(({children}) => {
    const id_udaxihhe = useId()
const [cs_a, setCs_a] = useState("a0")



    return(
        jsx(Card_72cd623b,{tid:"a-out",value:cs_a},)
    )
});
Memocomponent_card_72cd623b_card_72cd623b_9ba0ddbe21efbd49351eafd7d03c73dd_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_9a9d462869c1c3a2ed87a1d9ca289cd7_72cd623b = memo(({children}) => {
    const ref_a_btn = useRef(null); refs["ref_a_btn"] = ref_a_btn;
const on_click_4762b935bc60eb4db5bb76b45fe8ac04 = useCallback(((_e) => (((...args) => ((() => (setCs_a("a-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"a-btn",onClick:on_click_4762b935bc60eb4db5bb76b45fe8ac04,ref:ref_a_btn},children)
    )
});
Button_button_9a9d462869c1c3a2ed87a1d9ca289cd7_72cd623b.displayName = "Button";

export const Bare_comp_4700990c4f1e8cc74ef947675766d707_72cd623b = memo(({children}) => {
    const id_xdvxrcsn = useId()
const [cs_b, setCs_b] = useState("b0")



    return(
        cs_b
    )
});
Bare_comp_4700990c4f1e8cc74ef947675766d707_72cd623b.displayName = "Bare";

export const Button_button_3c4b436bc1998843311bf8ba47065e06_72cd623b = memo(({children}) => {
    const ref_b_btn = useRef(null); refs["ref_b_btn"] = ref_b_btn;
const on_click_91b36984e0101b02842f1753a1c6562e = useCallback(((_e) => (((...args) => ((() => (setCs_b("b-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"b-btn",onClick:on_click_91b36984e0101b02842f1753a1c6562e,ref:ref_b_btn},children)
    )
});
Button_button_3c4b436bc1998843311bf8ba47065e06_72cd623b.displayName = "Button";

export const Bare_comp_de795589d1a73971545ed4e826f92664_72cd623b = memo(({children}) => {
    const id_bacghqta = useId()
const [cs_c, setCs_c] = useState("c0")



    return(
        null
    )
});
Bare_comp_de795589d1a73971545ed4e826f92664_72cd623b.displayName = "Bare";

export const Memocomponent_card_72cd623b_card_72cd623b_4f38b3f64e604877991f8709a7bd448b_72cd623b = memo(({children}) => {
    const id_bacghqta = useId()
const [cs_c, setCs_c] = useState("c0")



    return(
        jsx(Card_72cd623b,{tid:"c-out",value:cs_c},)
    )
});
Memocomponent_card_72cd623b_card_72cd623b_4f38b3f64e604877991f8709a7bd448b_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_b2f95dae56aaa36fa7cc266ee5f29df6_72cd623b = memo(({children}) => {
    const ref_c_btn = useRef(null); refs["ref_c_btn"] = ref_c_btn;
const on_click_8b464817de333fd5e42a501da808b4e7 = useCallback(((_e) => (((...args) => ((() => (setCs_c("c-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"c-btn",onClick:on_click_8b464817de333fd5e42a501da808b4e7,ref:ref_c_btn},children)
    )
});
Button_button_b2f95dae56aaa36fa7cc266ee5f29df6_72cd623b.displayName = "Button";

export const Memocomponent_card_72cd623b_card_72cd623b_9d9d91061de5b8e3ee68f8a3f8071ce2_72cd623b = memo(({children}) => {
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
Memocomponent_card_72cd623b_card_72cd623b_9d9d91061de5b8e3ee68f8a3f8071ce2_72cd623b.displayName = "MemoComponent_Card_72cd623b";

export const Button_button_660ecfdc8dfb3aa0c696caf89707efd3_72cd623b = memo(({children}) => {
    const ref_d_btn = useRef(null); refs["ref_d_btn"] = ref_d_btn;
const on_click_a4a683fa42d615a7ba8ab7f2bc1b4667 = useCallback(((_e) => (((...args) => ((() => (refs['_client_state_setCs_d']("d-clicked")))(({ ["button"] : _e?.["button"], ["buttons"] : _e?.["buttons"], ["client_x"] : _e?.["clientX"], ["client_y"] : _e?.["clientY"], ["alt_key"] : _e?.["altKey"], ["ctrl_key"] : _e?.["ctrlKey"], ["meta_key"] : _e?.["metaKey"], ["shift_key"] : _e?.["shiftKey"] }), ...args)))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("button",{id:"d-btn",onClick:on_click_a4a683fa42d615a7ba8ab7f2bc1b4667,ref:ref_d_btn},children)
    )
});
Button_button_660ecfdc8dfb3aa0c696caf89707efd3_72cd623b.displayName = "Button";

export const Input_input_baaf3073188951b0059d52cf3277847d_72cd623b = memo(({children}) => {
    const ref_f_in = useRef(null); refs["ref_f_in"] = ref_f_in;
const on_change_c466d020a2a5aac04b40b86241821ec8 = useCallback(((_e) => (((_e) => (setCs_f(_e?.["target"]?.["value"])))(_e))), [addEvents, ReflexEvent])
const id_dcmdllti = useId()
const [cs_f, setCs_f] = useState("")



    return(
        jsx("input",{id:"f-in",onChange:on_change_c466d020a2a5aac04b40b86241821ec8,ref:ref_f_in,value:(isNotNullOrUndefined(cs_f) ? cs_f : "")},)
    )
});
Input_input_baaf3073188951b0059d52cf3277847d_72cd623b.displayName = "Input";

export const Input_input_13ea9da625af01fd834fe89adcff9cd6_72cd623b = memo(({children}) => {
    const ref_g_in = useRef(null); refs["ref_g_in"] = ref_g_in;
const on_change_69ea10bd7cbcf910f2f53239b96f3b1f = useCallback(((_e) => (((_e) => (setCs_g(_e?.["target"]?.["value"])))(_e))), [addEvents, ReflexEvent])



    return(
        jsx("input",{id:"g-in",onChange:on_change_69ea10bd7cbcf910f2f53239b96f3b1f,ref:ref_g_in},)
    )
});
Input_input_13ea9da625af01fd834fe89adcff9cd6_72cd623b.displayName = "Input";

export const Bare_comp_6f1a86d83d8cfdaab2e93252013e64ae_72cd623b = memo(({children}) => {
    const id_zbxordmc = useId()
const [cs_g, setCs_g] = useState("")



    return(
        cs_g
    )
});
Bare_comp_6f1a86d83d8cfdaab2e93252013e64ae_72cd623b.displayName = "Bare";
