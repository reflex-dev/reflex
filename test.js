import {useEffect, useRef, useState} from "react"
import {useRouter} from "next/router"
import {E, connect, updateState, uploadFiles} from "/utils/state"
import "focus-visible/dist/focus-visible"
import {Button, Center, HStack, Heading, Image, Input, VStack, useColorMode} from "@chakra-ui/react"
import NextHead from "next/head"

const EVENT = "ws://localhost:8000/event"
export default function Component() {
const [state, setState] = useState({"count": 0, "events": [{"name": "state.hydrate"}], "files": []})
const [result, setResult] = useState({"state": null, "events": [], "processing": false})
const router = useRouter()
const socket = useRef(null)
const { isReady } = router;
const { colorMode, toggleColorMode } = useColorMode()
const Event = events => setState({
  ...state,
  events: [...state.events, ...events],
})
const File = e => setState({...state, files: e.target.files})
useEffect(() => {
  if(!isReady) {
    return;
  }
  if (!socket.current) {
    connect(socket, state, setState, result, setResult, router, EVENT, ['websocket', 'polling'])
  }
  const update = async () => {
    if (result.state != null) {
      setState({
        ...result.state,
        events: [...state.events, ...result.events],
      })
      setResult({
        state: null,
        events: [],
        processing: false,
      })
    }
    await updateState(state, setState, result, setResult, router, socket.current)
  }
  update()
})
return (
<Center sx={{"paddingY": "5em", "fontSize": "2em", "textAlign": "center"}}><VStack sx={{"padding": "1em", "bg": "#ededed", "borderRadius": "1em", "boxShadow": "lg"}}><Heading>{state.count}</Heading>
<HStack><Button colorScheme="red"
onClick={() => Event([E("state.decrement", {})])}>{`Decrement`}</Button>
<Button onClick={() => Event([E("state.random", {})])}
sx={{"backgroundImage": "linear-gradient(90deg, rgba(255,0,0,1) 0%, rgba(0,176,34,1) 100%)", "color": "white"}}>{`Randomize`}</Button>
<Button colorScheme="green"
onClick={() => Event([E("state.increment", {})])}>{`Increment`}</Button></HStack>
<Input type="file"
onChange={e => File(e)}
<Button onClick={() => uploadFiles(state.files)}>{`Upload`}</Button>
<Image src="img.png" />
</VStack>
<NextHead><title>{`Counter`}</title>
<meta content="A Pynecone app."
name="description"/>
<meta content="favicon.ico"
property="og:image"/></NextHead></Center>
)
}