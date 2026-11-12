import { Suspense } from "react";

import { LoginForm } from "./login-form";

// The form reads ?next= from the URL, so it renders behind a Suspense boundary.
export default function Page() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
