
import {ReflexEvent,applyEventActions,getRefValue,getRefValues,isTrue,refs} from "$/utils/state"
import {Button as RadixThemesButton,Text as RadixThemesText} from "@radix-ui/themes"
import {jsx} from "@emotion/react"
import {Fragment,memo,useCallback,useContext,useEffect} from "react"
import {StateContexts,UploadFilesContext,addEvents} from "$/utils/context"
import {} from "react-dropzone"
import {useDropzone} from "react-dropzone"
import {Root as RadixFormRoot} from "@radix-ui/react-form"








export const MemoChip_bade3042 = memo(({iid:iidRxMemo}) => {
    
const chip_label = iidRxMemo;


    return(
        jsx("div",{"data-chip":"1",label:iidRxMemo},jsx(RadixThemesText,{as:"p"},iidRxMemo))
    )
});
MemoChip_bade3042.displayName = "MemoChip";

export const Foreach_comp_3ea64a0e60526946bae615508a2075ea_bade3042 = memo(({children}) => {
    
const chip_label = iid_rx_state_;


    return(
        Array.prototype.map.call(["a", "b"] ?? [],((iid_rx_state_,index_f1c15ad9a34b3be7d5b60d036343637e)=>(jsx("div",{"data-chip":"1",key:index_f1c15ad9a34b3be7d5b60d036343637e,label:iid_rx_state_},jsx(RadixThemesText,{as:"p"},iid_rx_state_)))))
    )
});
Foreach_comp_3ea64a0e60526946bae615508a2075ea_bade3042.displayName = "Foreach";

export const Foreach_comp_c6156ae8625554bb43b6741c7117db65_bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(StateContexts.reflex___state____state__pureforeach___pureforeach___s)
const chip_label = iid_rx_state_;


    return(
        Array.prototype.map.call(reflex___state____state__pureforeach___pureforeach___s.items_rx_state_ ?? [],((iid_rx_state_,index_f1c15ad9a34b3be7d5b60d036343637e)=>(jsx("div",{"data-chip":"1",key:index_f1c15ad9a34b3be7d5b60d036343637e,label:iid_rx_state_},jsx(RadixThemesText,{as:"p"},iid_rx_state_)))))
    )
});
Foreach_comp_c6156ae8625554bb43b6741c7117db65_bade3042.displayName = "Foreach";

export const Foreach_comp_2bfb8d297f1bde5b3a1ac17018c166bf_bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(StateContexts.reflex___state____state__pureforeach___pureforeach___s)
const [filesById, setFilesById] = useContext(UploadFilesContext);
const on_drop_15ea36af2ea3d923db7dd5a3d626ce12 = useCallback(((_ev_0) => ((e => setFilesById(filesById => {
    const updatedFilesById = Object.assign({}, filesById);
    updatedFilesById[iid_rx_state_] = e;
    return updatedFilesById;
  })
    )(_ev_0))), [addEvents, ReflexEvent, filesById, setFilesById])
const on_drop_rejected_2fcedbdc0771e7617b4270e2d1ac8cc9 = useCallback(((_ev_0) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (refs['__toast']?.["error"]("", ({ ["title"] : "Files not Accepted", ["description"] : _ev_0.map(((osizayzf) => (osizayzf?.["file"]?.["path"]+": "+osizayzf?.["errors"].map(((wnkiegyk) => wnkiegyk?.["message"])).join(", ")))).join("\n\n"), ["closeButton"] : true, ["style"] : ({ ["whiteSpace"] : "pre-line" }) })))), ["callback"] : null }), ({  })))], [_ev_0], ({  })))), [addEvents, ReflexEvent])
const { getRootProps: xdvxrcsn, getInputProps: udaxihhe, isDragActive: bacghqta} = useDropzone(({ ["multiple"] : true, ["id"] : iid_rx_state_, ["onDrop"] : on_drop_15ea36af2ea3d923db7dd5a3d626ce12, ["onDropRejected"] : on_drop_rejected_2fcedbdc0771e7617b4270e2d1ac8cc9 }));



    return(
        Array.prototype.map.call(reflex___state____state__pureforeach___pureforeach___s.items_rx_state_ ?? [],((iid_rx_state_,index_c64576a8b7ad414048ae92db5943ba41)=>(jsx(Fragment,{key:index_c64576a8b7ad414048ae92db5943ba41},jsx("div",{className:"rx-Upload",css:({ ["border"] : "1px dashed var(--accent-12)", ["padding"] : "5em", ["textAlign"] : "center" }),"data-chip":"1",id:iid_rx_state_,...xdvxrcsn()},jsx("input",{type:"file",...udaxihhe()},),jsx(RadixThemesText,{as:"p"},iid_rx_state_))))))
    )
});
Foreach_comp_2bfb8d297f1bde5b3a1ac17018c166bf_bade3042.displayName = "Foreach";

export const Foreach_comp_1eed6a93d2fa41592eeda71da66c51b6_bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(StateContexts.reflex___state____state__pureforeach___pureforeach___s)

    const handleSubmit_2603bbbc146ee5200c991a0ace979d70 = useCallback((ev) => {
        const $form = ev.target
        ev.preventDefault()
        const form_data = {...Object.fromEntries(new FormData($form).entries()), ...({  })};

        (((...args) => (addEvents([(ReflexEvent("reflex___state____state.pureforeach___pureforeach___s.note", ({ ["value"] : iid_rx_state_ }), ({  })))], args, ({  }))))(ev));

        if (false) {
            $form.reset()
        }
    })
    


    return(
        Array.prototype.map.call(reflex___state____state__pureforeach___pureforeach___s.items_rx_state_ ?? [],((iid_rx_state_,index_d6f56d973b9f47163fe1d3f64dad7715)=>(jsx(RadixFormRoot,{className:"Root ",css:({ ["width"] : "100%" }),"data-chip":"1",key:index_d6f56d973b9f47163fe1d3f64dad7715,onSubmit:handleSubmit_2603bbbc146ee5200c991a0ace979d70},jsx("input",{name:"v"},),jsx("button",{type:"submit"},"go")))))
    )
});
Foreach_comp_1eed6a93d2fa41592eeda71da66c51b6_bade3042.displayName = "Foreach";

export const Bare_comp_2374b03927d7affb8f5ddb0197194adc_bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(StateContexts.reflex___state____state__pureforeach___pureforeach___s)



    return(
        reflex___state____state__pureforeach___pureforeach___s.log_rx_state_
    )
});
Bare_comp_2374b03927d7affb8f5ddb0197194adc_bade3042.displayName = "Bare";

export const Foreach_comp_60f699d43a10fb41f36878f9d3c1be2e_bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(StateContexts.reflex___state____state__pureforeach___pureforeach___s)



    return(
        Array.prototype.map.call(reflex___state____state__pureforeach___pureforeach___s.items_rx_state_ ?? [],((iid_rx_state_,index_87c28c1223ec7457e9f9bb8e8533c626)=>(jsx(RadixThemesButton,{"data-chip":"1",key:index_87c28c1223ec7457e9f9bb8e8533c626,onClick:((_e) => (addEvents([(ReflexEvent("reflex___state____state.pureforeach___pureforeach___s.note", ({ ["value"] : iid_rx_state_ }), ({  })))], [_e], ({  }))))},iid_rx_state_))))
    )
});
Foreach_comp_60f699d43a10fb41f36878f9d3c1be2e_bade3042.displayName = "Foreach";
