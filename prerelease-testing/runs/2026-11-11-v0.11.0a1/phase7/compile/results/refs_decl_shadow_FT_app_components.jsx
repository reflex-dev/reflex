
import {isTrue,useRegisteredRef} from "$/utils/state"
import {Fragment,memo,useEffect} from "react"
import {Text as RadixThemesText} from "@radix-ui/themes"
import {jsx} from "@emotion/react"



const refs = {mine: true};


export const ref_kind_17d1e908 = (() => String(typeof refs['ref_target']));



export const HookMemo_17d1e908 = /*#__PURE__*/ (() => {
const HookMemo_17d1e908 = memo(({label:labelRxMemo}) => {
    const ref_memolabel = useRegisteredRef("ref_memolabel");
useEffect(() => { refs['ref_target'].current.value = 'set by hook'; }, [])
    return(
        jsx(Fragment,{},jsx(RadixThemesText,{as:"p",id:"memolabel",ref:ref_memolabel},labelRxMemo),jsx(Fragment,{},))
    )
});
HookMemo_17d1e908.displayName = "HookMemo";
return HookMemo_17d1e908;
})();

export const Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908 = /*#__PURE__*/ (() => {
const Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908 = memo(({children}) => {
    useEffect(() => { refs['ref_target'].current.value = 'set by hook'; }, [])
    return(
        jsx(Fragment,{},)
    )
});
Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908.displayName = "RefHook";
return Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908;
})();

export const Refsdecl_fragment_89c7e3acc50e90efec3367351568b0a5_17d1e908 = /*#__PURE__*/ (() => {
const Refsdecl_fragment_89c7e3acc50e90efec3367351568b0a5_17d1e908 = memo(({children}) => {
    const __mine = refs.mine;
    return(
        jsx(Fragment,{},)
    )
});
Refsdecl_fragment_89c7e3acc50e90efec3367351568b0a5_17d1e908.displayName = "RefsDecl";
return Refsdecl_fragment_89c7e3acc50e90efec3367351568b0a5_17d1e908;
})();
