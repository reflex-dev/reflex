import { useColorMode as chakraUseColorMode } from "@chakra-ui/react"
import { useTheme } from "next-themes"
import { useEffect } from "react"
import { ColorModeContext } from "/utils/context.js"

export default function ChakraColorModeProvider({ children }) {
  const {colorMode, toggleColorMode} = chakraUseColorMode()
  const {theme, setTheme} = useTheme()

  useEffect(() => {
    if (colorMode != theme) {
        toggleColorMode()
    }
  }, [theme])

  return (
    <ColorModeContext.Provider value={[ colorMode, toggleColorMode ]}>
      {children}
    </ColorModeContext.Provider>
  )
}