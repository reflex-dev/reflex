import Router from "next/router";
import { useEffect, useState } from "react";

export default function Custom404() {
  const [isNotFound, setIsNotFound] = useState(false);

  useEffect(() => {
    const pathNameArray = window.location.pathname.split("/");
    if (pathNameArray.length == 2 && pathNameArray[1] == "404") {
      setIsNotFound(true);
    } else {
      Router.replace(window.location.pathname);
    }
  }, []);

  if (isNotFound) return <h1>404 - Page Not Found</h1>;

  return null;
}
