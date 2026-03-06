--[[
  Ozone_GetSet_Params.lua
  Пример: чтение/запись ограниченных параметров Ozone на мастер-шине (Maximizer Amount, Dynamics Amount).
  Индексы параметров зависят от версии Ozone; здесь условные индексы — подставьте по факту через Reaper FX browser.
  Использование: вызвать из приложения через Reaper API или вручную для проверки.
]]

local master = reaper.GetMasterTrack(0)
if not master then return end

local fx_idx = -1
for i = 0, reaper.TrackFX_GetCount(master) - 1 do
  local _, name = reaper.TrackFX_GetFXName(master, i, "")
  if name and (name:find("Ozone") or name:find("ozone")) then
    fx_idx = i
    break
  end
end

if fx_idx < 0 then
  reaper.ShowMessageBox("Ozone не найден на мастер-шине.", "Ozone", 0)
  return
end

-- Безопасные параметры (индексы зависят от Ozone; типично: 0-based)
-- Maximizer Amount и Dynamics Amount — часто в начале списка
local num_params = reaper.TrackFX_GetNumParams(master, fx_idx)
local msg = "Ozone FX #" .. fx_idx .. ", параметров: " .. num_params
reaper.ShowMessageBox(msg, "Ozone params", 0)

-- Пример: установить параметр 0 в 1.0 (100%) — только если нужно
-- reaper.TrackFX_SetParam(master, fx_idx, 0, 1.0)
