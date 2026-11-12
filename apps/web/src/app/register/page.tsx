import { Suspense } from "react";

import { RegisterForm } from "./register-form";

// The form reads ?next= from the URL, so it renders behind a Suspense boundary.
export default function Page() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
