import { useEffect, useState } from "react";

import { getHealth } from "../api/client";


const initialState = { state: "checking", data: null };


export function useApiHealth() {
  const [health, setHealth] = useState(initialState);

  useEffect(() => {
    const controller = new AbortController();

    getHealth({ signal: controller.signal })
      .then((data) => setHealth({ state: "connected", data }))
      .catch(() => setHealth({ state: "unavailable", data: null }));

    return () => controller.abort();
  }, []);

  return health;
}

