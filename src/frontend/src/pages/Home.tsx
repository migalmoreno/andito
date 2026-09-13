import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Category } from "~/types";
import {
  ErrorContainer,
  LoadingContainer,
  NoDataContainer,
} from "~/components";
import { useNavigateToSubcategory } from "~/hooks";

export const HomePage = () => {
  const navigateToSubcategory = useNavigateToSubcategory();

  const {
    data: categories,
    isError,
    error,
    refetch,
  } = useQuery<Category[]>({
    queryKey: ["/categories"],
  });

  const defaultSubcategory = useMemo(() => {
    for (const category of categories ?? []) {
      const subcategory = category.subcategories.find(
        (sub) => sub.searchable === false && !sub.nsfw,
      );
      if (subcategory) return { category, subcategory };
    }
    return undefined;
  }, [categories]);

  useEffect(() => {
    if (!defaultSubcategory) return;
    navigateToSubcategory(
      defaultSubcategory.category.name,
      defaultSubcategory.subcategory,
      { replace: true },
    );
  }, [defaultSubcategory]);

  if (isError) {
    return <ErrorContainer error={error as Error} onReload={refetch} />;
  }

  if (!categories || defaultSubcategory) {
    return <LoadingContainer />;
  }

  return <NoDataContainer />;
};
