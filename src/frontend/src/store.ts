import { create } from "zustand";
import { Category, Extractor, SubCategory } from "./types";
import { persist, redux, createJSONStorage } from "zustand/middleware";
import type { StateStorage } from "zustand/middleware";

const LEGACY_STORE_KEY = "alegoria";

const localStorageWithLegacyFallback: StateStorage = {
  getItem: (name) => {
    const value = localStorage.getItem(name);
    if (value != null) return value;

    const legacy = localStorage.getItem(LEGACY_STORE_KEY);
    if (legacy != null) {
      localStorage.setItem(name, legacy);
      localStorage.removeItem(LEGACY_STORE_KEY);
    }
    return legacy;
  },
  setItem: (name, value) => localStorage.setItem(name, value),
  removeItem: (name) => localStorage.removeItem(name),
};

interface AppState {
  categories: Category[];
  enabledCategories: Category[];
  categoriesError: boolean;
  showMobileMenu: boolean;
  showSearchForm: boolean;
  activeCategory?: Category;
  activeSubCategory?: SubCategory;
  activeExtractor?: Extractor;
}

type AppStore = AppState & {
  dispatch: (action: AppAction) => AppAction;
};

type AppAction =
  | { type: "setCategories"; categories: Category[] }
  | { type: "setEnabledCategories"; categories: Category[] }
  | { type: "setCategoriesError"; error: boolean }
  | { type: "setActiveCategory"; category: Category }
  | { type: "setActiveSubCategory"; subcategory?: SubCategory }
  | { type: "setActiveExtractor"; extractor: Extractor }
  | { type: "showMobileMenu"; show: boolean }
  | { type: "showSearchForm"; show: boolean };

const appReducer = (state: AppState, action: AppAction): AppState => {
  switch (action.type) {
    case "setCategories":
      return { ...state, categories: action.categories };
    case "setEnabledCategories":
      return { ...state, enabledCategories: action.categories };
    case "setCategoriesError":
      return { ...state, categoriesError: action.error };
    case "setActiveCategory":
      return { ...state, activeCategory: action.category };
    case "setActiveSubCategory":
      return { ...state, activeSubCategory: action.subcategory };
    case "setActiveExtractor":
      return { ...state, activeExtractor: action.extractor };
    case "showMobileMenu":
      return { ...state, showMobileMenu: action.show };
    case "showSearchForm":
      return { ...state, showSearchForm: action.show };
    default:
      return state;
  }
};

const initialState: AppState = {
  categories: [],
  enabledCategories: [],
  categoriesError: false,
  showMobileMenu: false,
  showSearchForm: false,
};

export const useAppStore = create<AppStore>()(
  persist(redux(appReducer, initialState), {
    name: "andito",
    version: 0.5,
    storage: createJSONStorage(() => localStorageWithLegacyFallback),
    partialize: (state) => ({
      activeCategory: state.activeCategory,
      activeSubCategory: state.activeSubCategory,
    }),
  }),
);
