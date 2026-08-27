
// Draw descriptions.
// Blocks all inputs, until the key to close it is pressed.
// Based on 'EnterKey' class
class BlockingDescription_RT : Menu
{
	private native static void RT_DrawDescriptions( String rtkey );

	ListMenuItemTextItem_RT m_owner;
	String m_rtkey;

	void Init(Menu parent, ListMenuItemTextItem_RT owner, String rtkey)
	{
		Super.Init(parent);
		m_owner = owner;
		m_rtkey = rtkey;
		menuactive = Menu.WaitKey;	// There should be a better way to disable GUI capture...

		//Console.Printf("BlockingDescription_RT: OPEN\n");
	}

	override bool TranslateKeyboardEvents()
	{
		return false; 
	}

	override bool OnInputEvent(InputEvent ev)
	{
		if (ev.type == InputEvent.Type_KeyDown)
		{
			// tolower
			int ch = ev.KeyChar;
			ch = ch >= 65 && ch <91? ch + 32 : ch;

			if (ch == 102 || // 'f'
				ch ==  27 || // esc
				ch ==  13 || // enter
				ch ==   8)   // backspace
			{
				//Console.Printf("BlockingDescription_RT: CLOSE\n");
				menuactive = Menu.On;
				Close();
				return true;
			}
		}
		return false;
	}

	override void Drawer()
	{
		mParentMenu.Drawer();
		RT_DrawDescriptions( m_rtkey );
	}
}

class ListMenuItemTextItem_RT : ListMenuItemTextItem
{
	private native static void ApplyResolution(int width, int height, bool fullscreen);
	private native static void ValidateResolutions(in out Array<int> arrWidthHeight);
	private native static int GetCurrentWindowWidth();
	private native static int GetCurrentWindowHeight();
	private native static bool IsAvailable_DLSS2();
	private native static bool IsAvailable_DLSS3FG();
	private native static bool IsAvailable_FSR2();
	private native static bool IsAvailable_FSR3FG();
	private native static bool IsAvailable_DXGI();
	private native static bool IsHDRAvailable();
	private native static bool IsRtxRemix();
	private native static void RT_SetBool0( bool v );
	private native static bool RT_GetBool0();
	private native static bool RT_HasDescription( String rtkey );
	private native static bool RT_DrawDescriptionHotkey( int c );

	String m_rtkey;
	bool m_isgray;

	Array<int> m_arr_widthheight;
	int m_chosen_w;
	int m_chosen_h;

	bool m_description_requested;

	// keep last set, so switching from crt/pixelated back 
	// to dlss/fsr2 preserves the upscaling preset
	// Cvar -- because we can't have static variables here..
	// need to share between mode/preset buttons
	CVar m_lastupscale;

	void Init(ListMenuDescriptor desc, String rtkeyOrName, Name child = "", int param = 0)
	{
		m_isgray = false;
		m_description_requested = false;

		m_rtkey = "";
		if (child == "")
		{
			if (RT_GetLabelStrFrom(rtkeyOrName).Length() > 0)
			{
				m_rtkey = rtkeyOrName;
			}
		}

		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			UpdateResolutionList();
			m_chosen_w = 0;
			m_chosen_h = 0;
		}

		// default value is important, see notes at cvar definition
		m_lastupscale = CVar.FindCVar("_rt_cachedpreset");

		Super.Init(desc, rtkeyOrName, "", child, param);
	}

	override bool Selectable()
	{
		if (Super.Selectable())
		{
			if (!m_isgray)
			{
				return true;
			}
		}
		return false;
	}
	
	int FindIdOfResolution(int target_w, int target_h)
	{
		int count = m_arr_widthheight.Size() / 2;
		for (int i = 0; i < count; i++)
		{
			int w = m_arr_widthheight[i * 2];
			int h = m_arr_widthheight[i * 2 + 1];

			if (target_w == w && target_h == h)
			{
				return i;
			}
		}
		return -1;
	}

	int FindIdOfResolution_Nearest(int target_w, int target_h)
	{
		int nearest = -1;
		int nearest_w = 0;
		int nearest_h = 0;

		int count = m_arr_widthheight.Size() / 2;
		for (int i = 0; i < count; i++)
		{
			int w = m_arr_widthheight[i * 2];
			int h = m_arr_widthheight[i * 2 + 1];

			if (nearest >= 0)
			{
				if (abs(w - target_w) < abs(nearest_w - target_w) ||
					abs(h - target_h) < abs(nearest_h - target_h))
				{
					nearest = i;
					nearest_w = w;
					nearest_h = h;
				}
			}
			else
			{
				nearest = i;
				nearest_w = w;
				nearest_h = h;
			}
		}
		return nearest;
	}

	void UpdateResolutionList()
	{
		Array<int> sz;
		sz.Push(800);  sz.Push(600);  // 4:3
		sz.Push(1280); sz.Push(720);  // 16:9
		sz.Push(1280); sz.Push(1024); // 5:4
		sz.Push(1600); sz.Push(900);  // 16:9
		sz.Push(1920); sz.Push(1080); // 16:9
		sz.Push(2560); sz.Push(1080); // 21:9
		sz.Push(2560); sz.Push(1440); // 16:9
		sz.Push(3440); sz.Push(1440); // 21:9
		sz.Push(3840); sz.Push(2160); // 16:9

		ValidateResolutions(sz);
		m_arr_widthheight.Move(sz);
	}
	
	static String RT_GetLabelStrFrom(String rtkey)
	{
		if (rtkey == "RTMNU_WINDOW_RESOL")
		{
			return "Window Size";
		}
		if (rtkey == "RTMNU_VSYNC")
		{
			return "VSync";
		}
		if (rtkey == "RTMNU_DXGI")
		{
			return "Present";
		}
		if (rtkey == "RTMNU_HDR")
		{
			return "HDR";
		}
		if (rtkey == "RTMNU_MODE")
		{
			return "Mode";
		}
		if (rtkey == "RTMNU_PRESET")
		{
			return "Preset";
		}
		if (rtkey == "RTMNU_FRAMEGEN")
		{
			return "FrameGen";
		}
		if (rtkey == "RTMNU_CLASSIC")
		{
			return "Classic";
		}
		if (rtkey == "RTMNU_BLOOM")
		{
			return "Bloom";
		}
		if (rtkey == "RTMNU_HUD_STYLE")
		{
			return "HUD";
		}
		if (rtkey == "RTMNU_HUD_SIZE")
		{
			return "HUD Size";
		}
		if (rtkey == "RTMNU_HUD_CROSSHAIR")
		{
			return "Crosshair";
		}
		if (rtkey == "RTMNU_FLUID")
		{
			return "Fluid";
		}
		if (rtkey == "RTMNU_RAYRECONST")
		{
			return "Ray Reconstr.";
		}
		return "";
	}

	String RT_GetLabelStr()
	{
		let label = RT_GetLabelStrFrom(m_rtkey);
		if (label.Length() == 0)
		{
			return mText;
		}
		return label;
	}

	enum EAllValues
	{
		RTMNU_fail = -2,
		RTMNU_custom_value = -1,

		RTMNU_VSYNC_off = 0,
		RTMNU_VSYNC_on,

		RTMNU_DXGI_off,
		RTMNU_DXGI_on,

		RTMNU_HDR_off,
		RTMNU_HDR_on,

		RTMNU_MODE_dlss,
		RTMNU_MODE_fsr2,
		RTMNU_MODE_crt,
		RTMNU_MODE_vhs,
		RTMNU_MODE_crtvhs,
		RTMNU_MODE_200,
		RTMNU_MODE_200dither,
		RTMNU_MODE_480,
		RTMNU_MODE_480dither,
		RTMNU_MODE_taa,

		RTMNU_PRESET_none,
		RTMNU_PRESET_native,
		RTMNU_PRESET_quality,
		RTMNU_PRESET_balanced,
		RTMNU_PRESET_performance,
		RTMNU_PRESET_ultraperf,

		RTMNU_FRAMEGEN_off,
		RTMNU_FRAMEGEN_on,
		RTMNU_FRAMEGEN_skip,

		RTMNU_CLASSIC_off,
		RTMNU_CLASSIC_25,
		RTMNU_CLASSIC_50,
		RTMNU_CLASSIC_75,
		RTMNU_CLASSIC_on,

		RTMNU_BLOOM_off,
		RTMNU_BLOOM_on,

		RTMNU_HUD_STYLE_none,
		RTMNU_HUD_STYLE_simple,
		RTMNU_HUD_STYLE_classic,

		RTMNU_HUD_SIZE_smaller,
		RTMNU_HUD_SIZE_small,
		RTMNU_HUD_SIZE_default,
		RTMNU_HUD_SIZE_large,
		RTMNU_HUD_SIZE_larger,

		RTMNU_HUD_CROSSHAIR_off,
		RTMNU_HUD_CROSSHAIR_on,

		RTMNU_FLUID_off,
		RTMNU_FLUID_on,
		RTMNU_FLUID_groovy,
		
		RTMNU_RAYRECONST_off,
		RTMNU_RAYRECONST_on,
	};

	static bool RT_IsDLSS()
	{
		if (!IsAvailable_DLSS2() && !IsAvailable_DLSS3FG())
		{
			return false;
		}
		let cvar_dlss = CVar.FindCVar("rt_upscale_dlss");
		if (cvar_dlss)
		{
			let dlss = cvar_dlss.GetInt();
			return dlss > 0 && dlss <= 6;
		}
		return false;
	}

	static bool RT_IsDLSS3FrameGenActive()
	{
		let cvar_framegen = CVar.FindCVar("rt_framegen");
		let cvar_dlss     = CVar.FindCVar("rt_upscale_dlss");

		if (cvar_framegen && cvar_dlss)
		{
			if (cvar_framegen.GetInt() != 0 && cvar_dlss.GetInt() > 0 && IsAvailable_DLSS3FG())
			{
				return true;
			}
		}
		return false;
	}

	static bool RT_IsFSR3FrameGenActive()
	{
		let cvar_framegen = CVar.FindCVar("rt_framegen");
		let cvar_fsr      = CVar.FindCVar("rt_upscale_fsr2");

		if (cvar_framegen && cvar_fsr)
		{
			if (cvar_framegen.GetInt() != 0 && cvar_fsr.GetInt() > 0 && IsAvailable_FSR3FG())
			{
				return true;
			}
		}
		return false;
	}

	// show vsync as Off, when active DLSS3 FG
	static bool RT_IsForced_VsyncOff()
	{
		return RT_IsDLSS3FrameGenActive();
	}

	// show dxgi as On, when active FG
	static bool RT_IsForced_DxgiOn()
	{
		return RT_IsDLSS3FrameGenActive() || RT_IsFSR3FrameGenActive();
	}

	static bool Around(double value, double target)
	{
		return abs(value - target) < 0.01;
	}

	static EAllValues RT_MakeValueFromCvar(String rtkey)
	{
		if (rtkey == "RTMNU_WINDOW_RESOL")
		{
			// ignored
			return RTMNU_custom_value;
		}
		if (rtkey == "RTMNU_VSYNC")
		{
			if (RT_IsForced_VsyncOff())
			{
				return RTMNU_VSYNC_off;
			}

			let cvar = CVar.FindCVar("rt_vsync");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 0:  return RTMNU_VSYNC_off;
					default: return RTMNU_VSYNC_on;
				}
			}
		}
		if (rtkey == "RTMNU_DXGI")
		{
			if (RT_IsForced_DxgiOn())
			{
				return RTMNU_DXGI_on;
			}

			let cvar = CVar.FindCVar("rt_dxgi");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 0:  return RTMNU_DXGI_off;
					default: return RTMNU_DXGI_on;
				}
			}
		}
		if (rtkey == "RTMNU_HDR")
		{
			if (!IsHDRAvailable())
			{
				return RTMNU_HDR_off;
			}

			let cvar = CVar.FindCVar("rt_hdr");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 0:  return RTMNU_HDR_off;
					default: return RTMNU_HDR_on;
				}
			}
		}
		if (rtkey == "RTMNU_MODE")
		{
			let cvar_dlss    = CVar.FindCVar("rt_upscale_dlss");
			let cvar_fsr2    = CVar.FindCVar("rt_upscale_fsr2");
			let cvar_taa     = CVar.FindCVar("rt_remix_taa");
			let cvar_vintage = CVar.FindCVar("rt_ef_vintage");
			if (cvar_dlss && cvar_fsr2 && cvar_vintage && cvar_taa)
			{
				let dlss    = IsAvailable_DLSS2() || IsAvailable_DLSS3FG() ? cvar_dlss.GetInt() : 0;
				let fsr2    = IsAvailable_FSR2()  || IsAvailable_FSR3FG()  ? cvar_fsr2.GetInt() : 0;
				let vintage = cvar_vintage.GetInt();
				let taa     = cvar_taa.GetInt();
				
				if ((dlss > 0 && dlss <= 6) && fsr2 == 0 && vintage == 0)
				{
					return RTMNU_MODE_dlss;
				}
				if (dlss == 0 && (fsr2 > 0 && fsr2 <= 6) && vintage == 0)
				{
					return RTMNU_MODE_fsr2;
				}
				if (dlss == 0 && fsr2 == 0 && (taa > 0 && taa <= 6) && vintage == 0)
				{
					return RTMNU_MODE_taa;
				}
				if (vintage > 0)
				{
					switch (vintage)
					{
						case 1: return RTMNU_MODE_crt;		// RT_VINTAGE_CRT
						case 2: return RTMNU_MODE_vhs;		// RT_VINTAGE_VHS
						case 3: return RTMNU_MODE_crtvhs;	// RT_VINTAGE_VHS_CRT
						case 4: return RTMNU_MODE_200;		// RT_VINTAGE_200
						case 5: return RTMNU_MODE_200dither;// RT_VINTAGE_200_DITHER
						case 6: return RTMNU_MODE_480;		// RT_VINTAGE_480
						case 7: return RTMNU_MODE_480dither;// RT_VINTAGE_480_DITHER
						default: break;
					}
				}
				return RTMNU_custom_value;
			}
		}
		if (rtkey == "RTMNU_PRESET")
		{
			let cvar_dlss    = CVar.FindCVar("rt_upscale_dlss");
			let cvar_fsr2    = CVar.FindCVar("rt_upscale_fsr2");
			let cvar_taa     = CVar.FindCVar("rt_remix_taa");
			let cvar_vintage = CVar.FindCVar("rt_ef_vintage");
			if (cvar_dlss && cvar_fsr2 && cvar_vintage && cvar_taa)
			{
				let dlss    = IsAvailable_DLSS2() || IsAvailable_DLSS3FG() ? cvar_dlss.GetInt() : 0;
				let fsr2    = IsAvailable_FSR2()  || IsAvailable_FSR3FG()  ? cvar_fsr2.GetInt() : 0;
				let taa     = IsRtxRemix()                                 ?  cvar_taa.GetInt() : 0;
				let vintage = cvar_vintage.GetInt();

				if (dlss > 0 && fsr2 == 0 && taa == 0 && vintage == 0)
				{
					switch(dlss)
					{
						case 6: return RTMNU_PRESET_native;
						case 1: return RTMNU_PRESET_quality;
						case 2: return RTMNU_PRESET_balanced;
						case 3: return RTMNU_PRESET_performance;
						case 4: return RTMNU_PRESET_ultraperf;
						default: break;
					}
				}
				if (dlss == 0 && fsr2 > 0 && taa == 0 && vintage == 0)
				{
					switch(fsr2)
					{
						case 6: return RTMNU_PRESET_native;
						case 1: return RTMNU_PRESET_quality;
						case 2: return RTMNU_PRESET_balanced;
						case 3: return RTMNU_PRESET_performance;
						case 4: return RTMNU_PRESET_ultraperf;
						default: break;
					}
				}
				if (dlss == 0 && fsr2 == 0 && taa > 0 && vintage == 0)
				{
					switch(taa)
					{
						case 6: return RTMNU_PRESET_native;
						case 1: return RTMNU_PRESET_quality;
						case 2: return RTMNU_PRESET_balanced;
						case 3: return RTMNU_PRESET_performance;
						case 4: return RTMNU_PRESET_ultraperf;
						default: break;
					}
				}
				if (vintage > 0 && vintage <= 7)
				{
					return RTMNU_PRESET_none;
				}
				return RTMNU_custom_value;
			}
		}
		if (rtkey == "RTMNU_FRAMEGEN")
		{
			if (!IsAvailable_DLSS3FG() && !IsAvailable_FSR3FG())
			{
				return RTMNU_FRAMEGEN_off;
			}

			let cvar_framegen = CVar.FindCVar("rt_framegen");
			let cvar_dlss     = CVar.FindCVar("rt_upscale_dlss");
			let cvar_fsr2     = CVar.FindCVar("rt_upscale_fsr2");

			if (cvar_framegen && cvar_dlss && cvar_fsr2)
			{
				if ((cvar_dlss.GetInt() > 0 && IsAvailable_DLSS3FG()) ||
					(cvar_fsr2.GetInt() > 0 && IsAvailable_FSR3FG()))
				{
					switch(cvar_framegen.GetInt())
					{
						case -1: return RTMNU_FRAMEGEN_skip;
						case  1: return RTMNU_FRAMEGEN_on;
						default: return RTMNU_FRAMEGEN_off;
					}
				}
				return RTMNU_FRAMEGEN_off;
			}
		}
		if (rtkey == "RTMNU_CLASSIC")
		{
			let cvar = CVar.FindCVar("rt_classic");
			if (cvar)
			{
				let f = cvar.GetFloat();
				if (Around(f, 0.0)) return RTMNU_CLASSIC_off;
				if (Around(f, 0.3)) return RTMNU_CLASSIC_25;
				if (Around(f, 0.5)) return RTMNU_CLASSIC_50;
				if (Around(f, 0.7)) return RTMNU_CLASSIC_75;
				else                return RTMNU_CLASSIC_on;
			}
		}
		if (rtkey == "RTMNU_BLOOM")
		{
			let cvar = CVar.FindCVar("rt_bloom");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 0:  return RTMNU_BLOOM_off;
					default: return RTMNU_BLOOM_on;
				}
			}
		}
		if (rtkey == "RTMNU_HUD_STYLE")
		{
			let cvar = CVar.FindCVar("screenblocks");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 12: return RTMNU_HUD_STYLE_none;
					case 11: return RTMNU_HUD_STYLE_simple;
					case 10: return RTMNU_HUD_STYLE_classic;
					default: return RTMNU_custom_value;
				}
			}
		}
		if (rtkey == "RTMNU_HUD_SIZE")
		{
			let cvar = CVar.FindCVar("rt_hudscale");
			if (cvar)
			{
				let f = cvar.GetFloat();
				if (Around(f, 0.5)) return RTMNU_HUD_SIZE_smaller;
				if (Around(f, 0.7)) return RTMNU_HUD_SIZE_small;
				if (Around(f, 1.0)) return RTMNU_HUD_SIZE_default;
				if (Around(f, 1.3)) return RTMNU_HUD_SIZE_large;
				if (Around(f, 1.7)) return RTMNU_HUD_SIZE_larger;
				else          	    return RTMNU_custom_value;
			}
		}
		if (rtkey == "RTMNU_HUD_CROSSHAIR")
		{
			let cvar = CVar.FindCVar("crosshairon");
			if (cvar)
			{
				switch(cvar.GetInt())
				{
					case 0:  return RTMNU_HUD_CROSSHAIR_off;
					default: return RTMNU_HUD_CROSSHAIR_on;
				}
			}
		}
		if (rtkey == "RTMNU_FLUID")
		{
			let cvar        = CVar.FindCVar("rt_fluid");
			let cvar_groovy = CVar.FindCVar("rt_blood_groovy");
			if (cvar && cvar_groovy)
			{
				if (cvar.GetInt() == 0)
				{
					return RTMNU_FLUID_off;
				}
				
				if (cvar_groovy.GetInt() == 0)
				{
					return RTMNU_FLUID_on;
				}
				else
				{
					return RTMNU_FLUID_groovy;
				}
			}
		}
		if (rtkey == "RTMNU_RAYRECONST")
		{
			let cvar_dlss = CVar.FindCVar("rt_upscale_dlss");
			let cvar_rr   = CVar.FindCVar("rt_remix_rayreconstr");
			if (cvar_dlss && cvar_rr)
			{
				if (cvar_rr.GetInt() != 0 && cvar_dlss.GetInt() > 0)
				{
					return RTMNU_RAYRECONST_on;
				}
				else
				{
					return RTMNU_RAYRECONST_off;
				}
			}
		}
		return RTMNU_fail;
	}

	void RT_ApplyCvar(EAllValues value)
	{
		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			// ignored
		}
		else if (m_rtkey == "RTMNU_VSYNC")
		{
			let cvar = CVar.FindCVar("rt_vsync");
			let cvar_framegen = CVar.FindCVar("rt_framegen");
			if (cvar && cvar_framegen)
			{
				switch(value)
				{
					case RTMNU_VSYNC_off: cvar.SetBool(false); cvar_framegen.SetInt(0); break;
					case RTMNU_VSYNC_on:  cvar.SetBool(true);  cvar_framegen.SetInt(0); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_DXGI")
		{
			let cvar = CVar.FindCVar("rt_dxgi");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_DXGI_off: cvar.SetBool(false); break;
					case RTMNU_DXGI_on:  cvar.SetBool(true); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_HDR")
		{
			let cvar = CVar.FindCVar("rt_hdr");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_HDR_off: cvar.SetBool(false); break;
					case RTMNU_HDR_on:  cvar.SetBool(true); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_PRESET" || m_rtkey == "RTMNU_MODE")
		{
			let cvar_dlss    = CVar.FindCVar("rt_upscale_dlss");
			let cvar_fsr2    = CVar.FindCVar("rt_upscale_fsr2");
			let cvar_vintage = CVar.FindCVar("rt_ef_vintage");
			let cvar_framegen = CVar.FindCVar("rt_framegen");
			let cvar_taa     = CVar.FindCVar("rt_remix_taa");
			if (cvar_dlss && cvar_fsr2 && cvar_vintage && cvar_framegen && cvar_taa)
			{
				EAllValues mode = RTMNU_custom_value;
				EAllValues preset = RTMNU_custom_value;

				// need to know what upscaler / perf preset to apply
				if (m_rtkey == "RTMNU_MODE")
				{
					mode = value;
					preset = RT_MakeValueFromCvar("RTMNU_PRESET");
				}
				else
				{
					mode = RT_MakeValueFromCvar("RTMNU_MODE");
					preset = value;
				}

				switch(mode)
				{
					case RTMNU_MODE_dlss:
						cvar_framegen.SetInt(0);
						switch(preset)
						{
							case RTMNU_PRESET_native:      cvar_dlss.SetInt(6); m_lastupscale.SetInt(6);break;
							case RTMNU_PRESET_quality:     cvar_dlss.SetInt(1); m_lastupscale.SetInt(1);break;
							case RTMNU_PRESET_balanced:    cvar_dlss.SetInt(2); m_lastupscale.SetInt(2);break;
							case RTMNU_PRESET_performance: cvar_dlss.SetInt(3); m_lastupscale.SetInt(3);break;
							case RTMNU_PRESET_ultraperf:   cvar_dlss.SetInt(4); m_lastupscale.SetInt(4);break;
							default:                       cvar_dlss.SetInt(m_lastupscale.GetInt()); break;
						}
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(0);
						break;
					case RTMNU_MODE_fsr2:
						cvar_framegen.SetInt(0); // must be reset as there's a crash when switching quality, with FG=ON
						cvar_dlss.SetInt(0);
						cvar_taa.SetInt(0);
						switch(preset)
						{
							case RTMNU_PRESET_native:      cvar_fsr2.SetInt(6); m_lastupscale.SetInt(6); break;
							case RTMNU_PRESET_quality:     cvar_fsr2.SetInt(1); m_lastupscale.SetInt(1); break;
							case RTMNU_PRESET_balanced:    cvar_fsr2.SetInt(2); m_lastupscale.SetInt(2); break;
							case RTMNU_PRESET_performance: cvar_fsr2.SetInt(3); m_lastupscale.SetInt(3); break;
							case RTMNU_PRESET_ultraperf:   cvar_fsr2.SetInt(4); m_lastupscale.SetInt(4); break;
							default:                       cvar_fsr2.SetInt(m_lastupscale.GetInt()); break;
						}
						cvar_vintage.SetInt(0);
						break;
					case RTMNU_MODE_taa:
						cvar_framegen.SetInt(0); // must be reset as there's a crash when switching quality, with FG=ON
						cvar_dlss.SetInt(0);
						switch(preset)
						{
							case RTMNU_PRESET_native:       cvar_taa.SetInt(6); m_lastupscale.SetInt(6); break;
							case RTMNU_PRESET_quality:      cvar_taa.SetInt(1); m_lastupscale.SetInt(1); break;
							case RTMNU_PRESET_balanced:     cvar_taa.SetInt(2); m_lastupscale.SetInt(2); break;
							case RTMNU_PRESET_performance:  cvar_taa.SetInt(3); m_lastupscale.SetInt(3); break;
							case RTMNU_PRESET_ultraperf:    cvar_taa.SetInt(4); m_lastupscale.SetInt(4); break;
							default:                        cvar_taa.SetInt(m_lastupscale.GetInt()); break;
						}
						cvar_fsr2.SetInt(0);
						cvar_vintage.SetInt(0);
						break;
					case RTMNU_MODE_crt:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(1);
						break;
					case RTMNU_MODE_vhs:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(2);
						break;
					case RTMNU_MODE_crtvhs:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(3);
						break;
					case RTMNU_MODE_200:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(4);
						break;
					case RTMNU_MODE_200dither:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(5);
						break;
					case RTMNU_MODE_480:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(6);
						break;
					case RTMNU_MODE_480dither:  
						cvar_framegen.SetInt(0);
						cvar_dlss.SetInt(0);
						cvar_fsr2.SetInt(0);
						cvar_taa.SetInt(0);
						cvar_vintage.SetInt(7);
						break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_FRAMEGEN")
		{
			let cvar = CVar.FindCVar("rt_framegen");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_FRAMEGEN_off:  cvar.SetInt(0); break;
					case RTMNU_FRAMEGEN_on:   cvar.SetInt(1); break;
					case RTMNU_FRAMEGEN_skip: cvar.SetInt(-1); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_CLASSIC")
		{
			let cvar = CVar.FindCVar("rt_classic");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_CLASSIC_off: cvar.SetFloat(0.0); break;
					case RTMNU_CLASSIC_25:  cvar.SetFloat(0.3); break;
					case RTMNU_CLASSIC_50:  cvar.SetFloat(0.5); break;
					case RTMNU_CLASSIC_75:  cvar.SetFloat(0.7); break;
					case RTMNU_CLASSIC_on:  cvar.SetFloat(1.0); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_BLOOM")
		{
			let cvar = CVar.FindCVar("rt_bloom");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_BLOOM_off: cvar.SetBool(false); break;
					case RTMNU_BLOOM_on:  cvar.SetBool(true); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_HUD_STYLE")
		{
			let cvar = CVar.FindCVar("screenblocks");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_HUD_STYLE_none:    cvar.SetInt(12); break;
					case RTMNU_HUD_STYLE_simple:  cvar.SetInt(11); break;
					case RTMNU_HUD_STYLE_classic: cvar.SetInt(10); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_HUD_SIZE")
		{
			let cvar = CVar.FindCVar("rt_hudscale");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_HUD_SIZE_smaller: cvar.SetFloat(0.5); break;
					case RTMNU_HUD_SIZE_small:   cvar.SetFloat(0.7);  break;
					case RTMNU_HUD_SIZE_default: cvar.SetFloat(1.0);  break;
					case RTMNU_HUD_SIZE_large:   cvar.SetFloat(1.3);  break;
					case RTMNU_HUD_SIZE_larger:  cvar.SetFloat(1.7); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_HUD_CROSSHAIR")
		{
			let cvar = CVar.FindCVar("crosshairon");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_HUD_CROSSHAIR_off: cvar.SetBool(false); break;
					case RTMNU_HUD_CROSSHAIR_on:  cvar.SetBool(true); break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_FLUID")
		{
			let cvar        = CVar.FindCVar("rt_fluid");
			let cvar_groovy = CVar.FindCVar("rt_blood_groovy");
			if (cvar && cvar_groovy)
			{
				switch(value)
				{
					case RTMNU_FLUID_off:
						cvar.SetBool(false);
						cvar_groovy.SetBool(false);
						break;
					case RTMNU_FLUID_on:
						cvar.SetBool(true);
						cvar_groovy.SetBool(false);
						break;
					case RTMNU_FLUID_groovy:
						cvar.SetBool(true);
						cvar_groovy.SetBool(true);
						break;
					default: break;
				}
			}
		}
		else if (m_rtkey == "RTMNU_RAYRECONST")
		{
			let cvar = CVar.FindCVar("rt_remix_rayreconstr");
			if (cvar)
			{
				switch(value)
				{
					case RTMNU_RAYRECONST_off: cvar.SetBool(false); break;
					case RTMNU_RAYRECONST_on:  cvar.SetBool(true); break;
					default: break;
				}
			}
		}
	}

	EAllValues RT_GetNextOrPrevCvarValue(EAllValues cur, bool toleft)
	{
		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			// ignored
		}
		if (m_rtkey == "RTMNU_VSYNC")
		{
			switch(cur)
			{
				case RTMNU_VSYNC_off: return RTMNU_VSYNC_on;
				default:              return RTMNU_VSYNC_off;
			}
		}
		if (m_rtkey == "RTMNU_DXGI")
		{
			switch(cur)
			{
				case RTMNU_DXGI_off:  return RTMNU_DXGI_on;
				default:              return RTMNU_DXGI_off;
			}
		}
		if (m_rtkey == "RTMNU_HDR")
		{
			switch(cur)
			{
				case RTMNU_HDR_off: return RTMNU_HDR_on;
				default:            return RTMNU_HDR_off;
			}
		}
		if (m_rtkey == "RTMNU_MODE")
		{
			if (IsRtxRemix())
			{
				switch(cur)
				{
					case RTMNU_MODE_taa: return RTMNU_MODE_dlss;
					default:             return RTMNU_MODE_taa;
				}
			}

			Array<int> stack;

			if (IsAvailable_DLSS2())
			{
				stack.Push(RTMNU_MODE_dlss);
			}
			if (IsAvailable_FSR2())
			{
				stack.Push(RTMNU_MODE_fsr2);
			}
			stack.Push(RTMNU_MODE_crt);
			stack.Push(RTMNU_MODE_crtvhs);
			stack.Push(RTMNU_MODE_vhs);
			stack.Push(RTMNU_MODE_200dither);
			stack.Push(RTMNU_MODE_200);
			stack.Push(RTMNU_MODE_480dither);
			stack.Push(RTMNU_MODE_480);

			int found = -1;
			for (int i = 0; i < stack.Size(); i++)
			{
				if (cur == stack[i])
				{
					found = i;
				}
			}

			if (found < 0 && found >= stack.Size())
			{
				return RTMNU_MODE_480dither;
			}

			int next = clamp(found + (toleft ? -1 : +1), //
							 0, stack.Size() - 1);
			return stack[next];
		}
		if (m_rtkey == "RTMNU_PRESET")
		{
			switch(cur)
			{
				case RTMNU_PRESET_none:        return toleft ? RTMNU_PRESET_none        : RTMNU_PRESET_none;
				case RTMNU_PRESET_ultraperf:   return toleft ? RTMNU_PRESET_ultraperf   : RTMNU_PRESET_performance;
				case RTMNU_PRESET_performance: return toleft ? RTMNU_PRESET_ultraperf   : RTMNU_PRESET_balanced;
				case RTMNU_PRESET_balanced:    return toleft ? RTMNU_PRESET_performance : RTMNU_PRESET_quality;
				case RTMNU_PRESET_quality:     return toleft ? RTMNU_PRESET_balanced    : RTMNU_PRESET_native;
				case RTMNU_PRESET_native:      return toleft ? RTMNU_PRESET_quality     : RTMNU_PRESET_native;
				default: return RTMNU_PRESET_balanced;
			}
		}
		if (m_rtkey == "RTMNU_FRAMEGEN")
		{
			switch(cur)
			{
				case RTMNU_FRAMEGEN_off: return RTMNU_FRAMEGEN_on;
				default:                 return RTMNU_FRAMEGEN_off;
			}
		}
		if (m_rtkey == "RTMNU_CLASSIC")
		{
			switch(cur)
			{
				case RTMNU_CLASSIC_off: return toleft ? RTMNU_CLASSIC_off : RTMNU_CLASSIC_50;
				case RTMNU_CLASSIC_50:  return toleft ? RTMNU_CLASSIC_off : RTMNU_CLASSIC_on;
				case RTMNU_CLASSIC_on:  return toleft ? RTMNU_CLASSIC_50  : RTMNU_CLASSIC_on;
				// ignoring these
				case RTMNU_CLASSIC_25:  return toleft ? RTMNU_CLASSIC_off : RTMNU_CLASSIC_50;
				case RTMNU_CLASSIC_75:  return toleft ? RTMNU_CLASSIC_50  : RTMNU_CLASSIC_on;
				default: return RTMNU_CLASSIC_off;
			}
		}
		if (m_rtkey == "RTMNU_BLOOM")
		{
			switch(cur)
			{
				case RTMNU_BLOOM_on: return RTMNU_BLOOM_off;
				default:             return RTMNU_BLOOM_on;
			}
		}
		if (m_rtkey == "RTMNU_HUD_STYLE")
		{
			switch(cur)
			{
				case RTMNU_HUD_STYLE_none:    return toleft ? RTMNU_HUD_STYLE_none    : RTMNU_HUD_STYLE_simple;
				case RTMNU_HUD_STYLE_simple:  return toleft ? RTMNU_HUD_STYLE_none    : RTMNU_HUD_STYLE_classic;
				case RTMNU_HUD_STYLE_classic: return toleft ? RTMNU_HUD_STYLE_simple  : RTMNU_HUD_STYLE_classic;
				default: return RTMNU_HUD_STYLE_simple;
			}
		}
		if (m_rtkey == "RTMNU_HUD_SIZE")
		{
			switch(cur)
			{
				case RTMNU_HUD_SIZE_smaller: return toleft ? RTMNU_HUD_SIZE_smaller : RTMNU_HUD_SIZE_small;
				case RTMNU_HUD_SIZE_small:   return toleft ? RTMNU_HUD_SIZE_smaller : RTMNU_HUD_SIZE_default;
				case RTMNU_HUD_SIZE_default: return toleft ? RTMNU_HUD_SIZE_small   : RTMNU_HUD_SIZE_large;
				case RTMNU_HUD_SIZE_large:   return toleft ? RTMNU_HUD_SIZE_default : RTMNU_HUD_SIZE_larger;
				case RTMNU_HUD_SIZE_larger:  return toleft ? RTMNU_HUD_SIZE_large   : RTMNU_HUD_SIZE_larger;
				default: return RTMNU_HUD_SIZE_default;
			}
		}
		if (m_rtkey == "RTMNU_HUD_CROSSHAIR")
		{
			switch(cur)
			{
				case RTMNU_HUD_CROSSHAIR_on: return RTMNU_HUD_CROSSHAIR_off;
				default:                     return RTMNU_HUD_CROSSHAIR_on;
			}
		}
		if (m_rtkey == "RTMNU_FLUID")
		{
			switch(cur)
			{
				case RTMNU_FLUID_off:    return toleft ? RTMNU_FLUID_off : RTMNU_FLUID_on;
				case RTMNU_FLUID_on:     return toleft ? RTMNU_FLUID_off : RTMNU_FLUID_groovy;
				case RTMNU_FLUID_groovy: return toleft ? RTMNU_FLUID_on  : RTMNU_FLUID_groovy;
				default: return RTMNU_FLUID_off;
			}
		}
		if (m_rtkey == "RTMNU_RAYRECONST")
		{
			switch(cur)
			{
				case RTMNU_RAYRECONST_on: return RTMNU_RAYRECONST_off;
				default:                  return RTMNU_RAYRECONST_on;
			}
		}
		return RTMNU_fail;
	}

	String RT_ValueToString(EAllValues e)
	{
		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			UpdateResolutionList();
			int maxid = (m_arr_widthheight.Size() / 2) - 1;

			int resolution = FindIdOfResolution(m_chosen_w, m_chosen_h);

			int w = 0;
			int h = 0;
			if (resolution >= 0 && resolution <= maxid)
			{
				w = m_arr_widthheight[resolution * 2];
				h = m_arr_widthheight[resolution * 2 + 1];
			}
			else
			{
				w = GetCurrentWindowWidth();
				h = GetCurrentWindowHeight();
			}

			return String.Format("%ix%i", w, h);
		}

		switch(e)
		{
			case RTMNU_VSYNC_off: 			return "Off";
			case RTMNU_VSYNC_on: 			return "On";
			case RTMNU_DXGI_off: 			return "Vulkan";
			case RTMNU_DXGI_on: 			return "DXGI";
			case RTMNU_HDR_off:				return "Off";
			case RTMNU_HDR_on:				return "On";
			// Upstream said "DLSS 2" / "DLSS 3" here, and neither is a version: the
			// 2/3 named the marketing TIER -- 2 = Super Resolution alone, 3 = SR plus
			// Frame Generation -- so the row read "DLSS 2" to every player who had FG
			// off. The shipped nvngx_dlss.dll is 310.7, a DLSS 4 runtime, so the label
			// was two majors stale: testers read it as "this game is on old DLSS".
			// Naming the FG state instead is true whatever DLL a user drops in; do NOT
			// hardcode a number here for the same reason. Twin: rt_cutscene.cpp
			// l_getmode() draws the same row on the first-start wizard.
			case RTMNU_MODE_dlss: 			return RT_IsDLSS3FrameGenActive() ? "DLSS + FG" : "DLSS";
			case RTMNU_MODE_fsr2: 			return RT_IsFSR3FrameGenActive() ? "FSR + FG" : "FSR";
			case RTMNU_MODE_taa: 			return "TAA";
			case RTMNU_MODE_crt: 			return "CRT";
			case RTMNU_MODE_vhs: 			return "VHS-P";
			case RTMNU_MODE_crtvhs:			return "VHS";
			case RTMNU_MODE_200: 			return "320x200";
			case RTMNU_MODE_200dither:		return "320x200x16";
			case RTMNU_MODE_480: 			return "640x480";
			case RTMNU_MODE_480dither:		return "640x480x16";
			case RTMNU_PRESET_none: 		return "None";
			case RTMNU_PRESET_native: 		return RT_IsDLSS() ? "DLAA": "Native";
			case RTMNU_PRESET_quality: 		return "Quality";
			case RTMNU_PRESET_balanced: 	return "Balanced";
			case RTMNU_PRESET_performance: 	return "Performance";
			case RTMNU_PRESET_ultraperf: 	return "Ultra Perf.";
			case RTMNU_FRAMEGEN_off:		return "Off";
			case RTMNU_FRAMEGEN_on:			return "On";
			case RTMNU_FRAMEGEN_skip:		return "On, but Skip Generated";
			case RTMNU_CLASSIC_off: 		return "Off";
			case RTMNU_CLASSIC_25: 			return "25%";
			case RTMNU_CLASSIC_50: 			return "50%";
			case RTMNU_CLASSIC_75: 			return "75%";
			case RTMNU_CLASSIC_on: 			return "On";
			case RTMNU_BLOOM_off: 			return "Off";
			case RTMNU_BLOOM_on: 			return "On";
			case RTMNU_HUD_STYLE_none: 		return "None";
			case RTMNU_HUD_STYLE_simple: 	return "Simple";
			case RTMNU_HUD_STYLE_classic: 	return "Classic";
			case RTMNU_HUD_SIZE_smaller: 	return "50%";
			case RTMNU_HUD_SIZE_small: 		return "75%";
			case RTMNU_HUD_SIZE_default: 	return "100%";
			case RTMNU_HUD_SIZE_large: 		return "150%";
			case RTMNU_HUD_SIZE_larger: 	return "200%";
			case RTMNU_HUD_CROSSHAIR_off:	return "Off";
			case RTMNU_HUD_CROSSHAIR_on:	return "On";
			case RTMNU_FLUID_off:			return "Off";
			case RTMNU_FLUID_on:			return "On";
			case RTMNU_FLUID_groovy:		return "Groovy.";
			case RTMNU_custom_value:		return "Custom";
			case RTMNU_RAYRECONST_off:		return RT_IsDLSS() ? "Off" : "--";
			case RTMNU_RAYRECONST_on:		return RT_IsDLSS() ? "On" : "--";
			default: 						return ">>>";
		}
	}

	override bool RT_Activate_LeftOrRight(bool toleft, bool justapply)
	{
		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			UpdateResolutionList();
			int maxid = (m_arr_widthheight.Size() / 2) - 1;

			if (m_chosen_w <= 0 || m_chosen_h <= 0)
			{
				m_chosen_w = GetCurrentWindowWidth();
				m_chosen_h = GetCurrentWindowHeight();
			}

			if (justapply)
			{
				int r = FindIdOfResolution(m_chosen_w, m_chosen_h);
				if (r >= 0 && r <= maxid)
				{
					int w = m_arr_widthheight[r * 2];
					int h = m_arr_widthheight[r * 2 + 1];
					bool fullscreen = false;

					//if (GetCurrentWindowWidth() != w &&
					//	GetCurrentWindowHeight() != h &&
					//	GetCurrentIsFullscreen() != fullscreen)
					{
						ApplyResolution(w, h, fullscreen);
					}
				}
				return true;
			}
			else
			{
				int r = FindIdOfResolution_Nearest(m_chosen_w, m_chosen_h);
				if (r >= 0 && maxid > 0)
				{
					r = r + (toleft ? -1 : +1);
					r = clamp(r, 0, maxid);
					m_chosen_w = m_arr_widthheight[r * 2];
					m_chosen_h = m_arr_widthheight[r * 2 + 1];
				}
				return false; // no sound effect
			}
		}

		let curValue = RT_MakeValueFromCvar(m_rtkey);

		let isbool = m_rtkey == "RTMNU_VSYNC"
		          // || m_rtkey == "RTMNU_DXGI"
		          || m_rtkey == "RTMNU_HDR"
		          || m_rtkey == "RTMNU_FRAMEGEN"
		          || m_rtkey == "RTMNU_BLOOM"
		          || m_rtkey == "RTMNU_CLASSIC"
		          || m_rtkey == "RTMNU_HUD_STYLE"
		          || m_rtkey == "RTMNU_RAYRECONST"
		          // || m_rtkey == "RTMNU_HUD_SIZE"
		          || m_rtkey == "RTMNU_HUD_CROSSHAIR";

		if (IsRtxRemix() && m_rtkey == "RTMNU_MODE")
		{
			isbool = true;
		}

		if (justapply && !isbool)
		{
			if (curValue != RTMNU_custom_value)
			{
				RT_ApplyCvar(curValue);
				return false; // no sound effect
			}
		}
		else
		{
			let nextValue = RT_GetNextOrPrevCvarValue(curValue, toleft);
			if (nextValue != RTMNU_fail && curValue != nextValue)
			{
				// if mode changes (e.g. FSR<->DLSS), force disable Frame Generation
				if (m_rtkey == "RTMNU_MODE")
				{
					let cvar = CVar.FindCVar("rt_framegen");
					if (cvar)
					{
						cvar.SetInt(0);
					}
				}

				RT_ApplyCvar(nextValue);
				return true;
			}
		}
		return false;
	}

	override bool Activate()
	{
		if (m_rtkey.Length() > 0)
		{
			return RT_Activate_LeftOrRight(false, true);
		}
		else
		{
			return Super.Activate();
		}
	}

	override void Draw(bool selected, ListMenuDescriptor desc)
	{
		if (selected && RT_GetBool0())
		{
			RT_SetBool0(false);
			if (RT_HasDescription(m_rtkey))
			{
				// create a new menu to show description and block inputs
				let input = new("BlockingDescription_RT");
				input.Init(Menu.GetCurrentMenu(), self, m_rtkey);
				input.ActivateMenu();
			}
		}

		int safe = 4;
		int selectorsize = 8;

		let font = menuDelegate.PickFont(mFont);

		let value = RT_MakeValueFromCvar(m_rtkey);
		m_isgray = (value == RTMNU_PRESET_none);

		if (m_rtkey == "RTMNU_HDR" && !IsHDRAvailable())
		{
			m_isgray = true;
		}

		if (m_rtkey == "RTMNU_FRAMEGEN")
		{
			m_isgray = true;

			let cvar_dlss = CVar.FindCVar("rt_upscale_dlss");
			let cvar_fsr2 = CVar.FindCVar("rt_upscale_fsr2");

			if (cvar_dlss && cvar_dlss.GetInt() > 0)
			{
				if (IsAvailable_DLSS3FG())
				{
					m_isgray = false;
				}
			}
			else if (cvar_fsr2 && cvar_fsr2.GetInt() > 0)
			{
				if (IsAvailable_FSR3FG())
				{
					m_isgray = false;
				}
			}
		}

		if (m_rtkey == "RTMNU_VSYNC")
		{
			if (RT_IsForced_VsyncOff())
			{
				m_isgray = true;
			}
		}

		if (m_rtkey == "RTMNU_DXGI")
		{
			if (RT_IsForced_DxgiOn())
			{
				m_isgray = true;
			}
		}

		if (m_rtkey == "RTMNU_RAYRECONST")
		{
			let cvar_dlss = CVar.FindCVar("rt_upscale_dlss");
			if (cvar_dlss && cvar_dlss.GetInt() <= 0)
			{
				m_isgray = true;
			}

			// HACKHACK: i failed... there's memory leak somewhere
			// don't let user enable / disable it in runtime :(
			m_isgray = true;
		}

		// label
		DrawText(
			desc, font, selected ? Font.CR_BRICK : Font.CR_WHITE,
			mXpos - GetWidth() - safe, mYpos, RT_GetLabelStr(),
			false, m_isgray);

		// value
		DrawText(
			desc, font, selected ? Font.CR_BRICK : Font.CR_WHITE,
			mXpos + selectorsize + safe, mYpos, RT_ValueToString(value),
			false, m_isgray);

		if (m_rtkey == "RTMNU_WINDOW_RESOL")
		{
			RT_DrawDescriptionHotkey(102); // 'f'
		}
	}

	// we explot that this is called on each menu event,
	// treating this as OnUIEvent
	override bool CheckHotkey(int ch)
	{ 
		if (ch == 102) // 'f'
		{
			RT_SetBool0(true);
		}
		return false;
	}

	override int GetWidth()
	{
		let font = menuDelegate.PickFont(mFont);
		return max(1, font.StringWidth(RT_GetLabelStr())); 
	}
}
