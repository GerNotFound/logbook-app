import React, { useEffect, useRef, useState } from "react";

interface FoodAutocompleteInputProps {
  availableFoods: string[];
  onFoodSelect: (food: string) => void;
  placeholder?: string;
  inputId?: string;
}

export const FoodAutocompleteInput: React.FC<FoodAutocompleteInputProps> = ({
  availableFoods,
  onFoodSelect,
  placeholder = "Cerca un alimento...",
  inputId,
}) => {
  const [inputValue, setInputValue] = useState("");
  const [filteredFoods, setFilteredFoods] = useState<string[]>([]);
  const [isFocused, setIsFocused] = useState(false);

  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!inputValue.trim()) {
      setFilteredFoods([]);
      return;
    }

    const normalizedInput = inputValue.toLowerCase();
    const matches = availableFoods
      .filter((food) => food.toLowerCase().includes(normalizedInput))
      .slice(0, 5);

    setFilteredFoods(matches);
  }, [availableFoods, inputValue]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setIsFocused(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setInputValue(value);
    onFoodSelect(value);

    if (!isFocused) {
      setIsFocused(true);
    }
  };

  const handleSuggestionClick = (food: string) => {
    setInputValue(food);
    setIsFocused(false);
    onFoodSelect(food);
  };

  const showSuggestions = isFocused && filteredFoods.length > 0;

  return (
    <div className="relative w-full" ref={wrapperRef}>
      <input
        id={inputId}
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder={placeholder}
        className="w-full rounded-md border border-slate-700 bg-slate-900 py-2 px-3 text-slate-100 placeholder-slate-400 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        aria-autocomplete="list"
        aria-expanded={showSuggestions}
        aria-controls={showSuggestions ? `${inputId ?? "food"}-suggestions` : undefined}
        role="combobox"
      />
      {showSuggestions && (
        <ul
          id={`${inputId ?? "food"}-suggestions`}
          className="absolute z-20 mt-2 max-h-60 w-full overflow-y-auto rounded-md border border-slate-700 bg-slate-900 py-1 shadow-lg"
          role="listbox"
        >
          {filteredFoods.map((food) => (
            <li
              key={food}
              role="option"
              aria-selected={false}
              className="cursor-pointer px-3 py-2 text-slate-100 hover:bg-slate-800"
              onMouseDown={(event) => {
                event.preventDefault();
                handleSuggestionClick(food);
              }}
            >
              {food}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default FoodAutocompleteInput;
