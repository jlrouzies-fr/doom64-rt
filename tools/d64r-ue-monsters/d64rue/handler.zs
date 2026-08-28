// Placement: convert a share of the monsters a map already spawned.
//
// WHY WorldLoaded AND NOT CheckReplacement.
// CheckReplacement is the obvious hook and it is the wrong one. It is handed the
// class and nothing else (gzdoom src/gamedata/info.cpp, PClassActor::
// GetReplacement), so it cannot see the map thing's TID or ACS special, cannot
// know where the thing stands, and cannot test whether the replacement would
// even fit. All four matter here: script-wired monsters must be left alone, and
// the Spider Mastermind is radius 128 in a game whose widest monster is 64, so
// it has to be able to decline a spot.
//
// At WorldLoaded the actor list is complete and TID/special/args/position are
// all set, so every one of those decisions is available.
//
// DETERMINISM. Selection runs off a private LCG seeded from the map, never off
// random(): a map must lay out identically on every load and on every client in
// a netgame. ThinkerIterator order is not contractual either, so candidates are
// sorted by position before anything is drawn.

const D64R_VILE_MAPS = "MAP15,MAP20,MAP23,MAP30,ABS05,OUT05,RDM05,REC05,RTR05,RTR10";
const D64R_MM_MAPS   = "MAP22,OUT10";

class D64R_UEMonsterHandler : EventHandler
{
	// --- deterministic RNG -------------------------------------------------
	private uint rngState;

	private void SeedRng(uint salt)
	{
		// levelnum alone collides across episodes (several share a number), so
		// the map name is folded in too.
		uint h = 2166136261;
		String nm = level.MapName;
		for (int i = 0; i < int(nm.Length()); i++)
		{
			h = (h ^ uint(nm.ByteAt(i))) * 16777619;
		}
		rngState = h ^ (uint(level.levelnum) * 2654435761) ^ salt;
		if (rngState == 0) rngState = 1;
	}

	private uint NextRand()
	{
		rngState = rngState * 1664525 + 1013904223;
		return rngState >> 8;          // the low bits of an LCG are poor
	}

	// --- helpers -----------------------------------------------------------

	// Retribution replaces the Doom monsters with its own 64* actors, so those
	// are what a map actually spawns. Fall back to the vanilla name so the pk3
	// still does something sane if Retribution is not the loaded mod.
	private static Class<Actor> Donor(Name retrib, Name vanilla)
	{
		Class<Actor> c = retrib;
		if (!c) c = vanilla;
		return c;
	}

	private static bool CVarBool(String name, bool def)
	{
		let cv = CVar.FindCVar(name);
		return cv ? (cv.GetInt() != 0) : def;
	}

	private static int CVarInt(String name, int def)
	{
		let cv = CVar.FindCVar(name);
		return cv ? cv.GetInt() : def;
	}

	// Comma-separated map list, matched case-insensitively against this map.
	private static bool MapListed(String cvarName, String fallback)
	{
		let cv = CVar.FindCVar(cvarName);
		String raw = cv ? cv.GetString() : fallback;
		if (raw.Length() == 0) raw = fallback;

		Array<String> parts;
		String up = raw.MakeUpper();
		up.Split(parts, ",");

		String here = level.MapName;
		here = here.MakeUpper();

		for (int i = 0; i < parts.Size(); i++)
		{
			String p = parts[i];
			p.Replace(" ", "");
			if (p.Length() > 0 && p == here) return true;
		}
		return false;
	}

	// Campaign position, used for the ramping shares. MAPnn uses its number; the
	// bonus episodes (ABS/OUT/RDM/REC/RTR/FUN) all sit after the main game, and
	// anything unrecognised is treated as late so a third-party map gets the
	// full roster rather than the MAP01 one.
	private static int MapTier()
	{
		String nm = level.MapName;
		String up = nm.MakeUpper();
		if (up.Length() == 5 && up.Left(3) == "MAP")
		{
			int n = up.Mid(3, 2).ToInt();
			if (n > 0) return n;
		}
		return 99;
	}

	// --- candidate gathering ----------------------------------------------

	private static bool Before(Actor a, Actor b)
	{
		if (a.pos.x != b.pos.x) return a.pos.x < b.pos.x;
		if (a.pos.y != b.pos.y) return a.pos.y < b.pos.y;
		return a.pos.z < b.pos.z;
	}

	private void Gather(Class<Actor> cls, out Array<Actor> outList)
	{
		outList.Clear();
		if (!cls) return;

		ThinkerIterator it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			// SUBCLASS, not exact class. An exact GetClass() test looks right and
			// silently matches nothing the moment another loaded pk3 subclasses
			// a donor -- and one already does: d64r-blood-persist.pk3 declares
			// "RTBloodNightmareImp : 64NightmareImp replaces 64NightmareImp"
			// (and the same for the Cacodemon, Arachnotron, Pain Elemental and
			// Spider Mastermind), so every Nightmare Imp in the game is really an
			// RTBloodNightmareImp and the exact test found zero of them.
			if (!(mo.GetClass() is cls)) continue;
			// ...but never re-collect our own, or the Sergeant pass would eat the
			// monsters the Chaingunner pass just made (both descend from
			// ShotgunGuy).
			String cn = mo.GetClassName();
			if (cn.Left(5) == "D64R_") continue;
			if (mo.health <= 0) continue;
			// Wired into the map's ACS -- a script counts it, or a line targets
			// it. Changing its class out from under the script breaks the map.
			if (mo.tid != 0 || mo.special != 0) continue;
			outList.Push(mo);
		}

		// Insertion sort on position: ThinkerIterator order is an implementation
		// detail, and the selection has to be reproducible.
		for (int i = 1; i < outList.Size(); i++)
		{
			Actor key = outList[i];
			int j = i - 1;
			while (j >= 0 && Before(key, outList[j]))
			{
				outList[j + 1] = outList[j];
				j--;
			}
			outList[j + 1] = key;
		}
	}

	private int CountOf(Class<Actor> cls)
	{
		Array<Actor> a;
		Gather(cls, a);
		return a.Size();
	}

	// --- the swap ----------------------------------------------------------

	// Returns the new actor, or null if it would not fit, in which case the
	// original is left untouched.
	private Actor SwapOne(Actor old, Class<Actor> newCls)
	{
		if (!newCls) return null;

		// The original is still standing on the spot, and it is SOLID, so a
		// naive TestMobjLocation() on the replacement collides with the very
		// monster it is replacing and refuses every single swap. Take the old
		// one out of the blockmap for the duration of the test and put it back
		// if the test says no.
		bool wasSolid = old.bSOLID;
		old.bSOLID = false;

		Actor nu = Actor.Spawn(newCls, old.pos, NO_REPLACE);
		if (!nu)
		{
			old.bSOLID = wasSolid;
			return null;
		}

		nu.angle = old.angle;
		nu.SpawnAngle = old.SpawnAngle;
		nu.SpawnPoint = old.SpawnPoint;
		nu.bAmbush = old.bAmbush;
		nu.CopyFriendliness(old, false);

		if (!nu.TestMobjLocation())
		{
			// Spawn() already counted it, so drop the count before destroying or
			// the map's monster total climbs and 100% becomes unreachable.
			nu.ClearCounters();
			nu.Destroy();
			old.bSOLID = wasSolid;
			return null;
		}

		old.ClearCounters();
		old.Destroy();
		return nu;
	}

	// Convert up to `want` candidates, chosen by a deterministic shuffle.
	// Returns how many took; a fit-test refusal does not consume a pick.
	private int Convert(Class<Actor> donorCls, Class<Actor> newCls, int want, uint salt, out int refused)
	{
		refused = 0;
		if (want <= 0) return 0;

		Array<Actor> cands;
		Gather(donorCls, cands);
		int n = cands.Size();
		if (n == 0) return 0;

		// Fisher-Yates over the index list, then take from the front. Doing it
		// this way rather than rolling a percentage per candidate makes the
		// count exact, which is what the per-map caps need.
		Array<int> idx;
		for (int i = 0; i < n; i++) idx.Push(i);
		SeedRng(salt);
		for (int i = n - 1; i > 0; i--)
		{
			int j = int(NextRand() % uint(i + 1));
			int t = idx[i]; idx[i] = idx[j]; idx[j] = t;
		}

		int done = 0;
		for (int k = 0; k < n && done < want; k++)
		{
			Actor old = cands[idx[k]];
			if (!old) continue;
			if (SwapOne(old, newCls)) done++;
			else refused++;
		}
		return done;
	}

	private static int Share(int count, int pct)
	{
		if (count <= 0 || pct <= 0) return 0;
		int want = (count * pct + 50) / 100;
		// A map with any candidates at all should get at least one, or a low
		// percentage silently does nothing on the smaller maps.
		if (want < 1) want = 1;
		return want;
	}

	// --- entry point -------------------------------------------------------

	override void WorldLoaded(WorldEvent e)
	{
		if (e.IsSaveGame || e.IsReopen) return;

		int dbgLevel = CVarInt("d64_ue_debug", 0);
		// d64_ue_debug 2: every monster class the map actually spawned, with
		// counts. The donor names are guesses about Retribution's actor set
		// until something prints them.
		if (dbgLevel >= 2)
		{
			Array<String> seen;
			Array<int> num;
			ThinkerIterator dit = ThinkerIterator.Create("Actor");
			Actor dmo;
			while (dmo = Actor(dit.Next()))
			{
				if (!dmo.bIsMonster) continue;
				String cn = dmo.GetClassName();
				int at = -1;
				for (int i = 0; i < seen.Size(); i++) { if (seen[i] == cn) { at = i; break; } }
				if (at < 0) { seen.Push(cn); num.Push(1); } else { num[at] = num[at] + 1; }
			}
			for (int i = 0; i < seen.Size(); i++)
			{
				Console.Printf("d64_ue roster %s: %s x%d", level.MapName, seen[i], num[i]);
			}
		}
		int before = level.total_monsters;

		if (!CVarBool("d64_ue_enable", true)) return;

		bool dbg = CVarBool("d64_ue_debug", false);
		int tier = MapTier();

		Class<Actor> shotgunGuy = Donor("64ShotgunGuy",   "ShotgunGuy");
		Class<Actor> nmImp      = Donor("64NightmareImp", "DoomImp");
		Class<Actor> hellKnight = Donor("64HellKnight",   "HellKnight");
		Class<Actor> baron      = Donor("64BaronOfHell",  "BaronOfHell");
		Class<Actor> cyber      = Donor("64Cyberdemon",   "Cyberdemon");
		Class<Actor> arach      = Donor("64Arachnotron",  "Arachnotron");
		Class<Actor> fatso      = Donor("64Fatso",        "Fatso");

		int madeChain = 0, madeSgt = 0, madeRev = 0, madeVile = 0, madeMM = 0;
		int refChain = 0, refSgt = 0, refRev = 0, refVile = 0, refMM = 0;

		// Snapshot the pools before any conversion, for the census below.
		int poolSgun = dbg ? CountOf(shotgunGuy) : 0;
		int poolNmImp = dbg ? CountOf(nmImp) : 0;
		int poolHK = dbg ? CountOf(hellKnight) : 0;
		int poolBaron = dbg ? CountOf(baron) : 0;

		// Chaingunner from MAP05, ramping 12% -> 22% across MAP05..MAP20.
		if (tier >= 5)
		{
			int pct = CVarInt("d64_ue_chaingunner_pct", 12);
			if (tier > 5)
			{
				int ramp = tier > 20 ? 15 : tier - 5;
				pct += (10 * ramp) / 15;
			}
			madeChain = Convert(shotgunGuy, "D64R_ChaingunGuy",
				Share(CountOf(shotgunGuy), pct), 0x5A17, refChain);
		}

		// Former Sergeant from MAP01, taken from what the Chaingunner left. The
		// two draw on the same pool, so the shares apply in sequence rather than
		// both against the original count -- otherwise a late map turns over
		// more than half its Shotgun Guys between them.
		if (tier >= 1)
		{
			madeSgt = Convert(shotgunGuy, "D64R_FormerSergeant",
				Share(CountOf(shotgunGuy), CVarInt("d64_ue_sergeant_pct", 35)),
				0x2B93, refSgt);
		}

		// Revenant from MAP10: Nightmare Imps first, then Hell Knights.
		if (tier >= 10)
		{
			int pct = CVarInt("d64_ue_revenant_pct", 10);
			madeRev = Convert(nmImp, "D64R_Revenant",
				Share(CountOf(nmImp), pct), 0x71C4, refRev);

			int r2 = 0;
			madeRev += Convert(hellKnight, "D64R_Revenant",
				Share(CountOf(hellKnight), (pct * 4) / 5), 0x71C5, r2);
			refRev += r2;
		}

		// Arch-Vile: one, and only on the listed maps. Baron first; Hell Knight
		// only where the map has no Baron -- MAP30 is the case that needs it.
		if (MapListed("d64_ue_archvile_maps", D64R_VILE_MAPS))
		{
			madeVile = Convert(baron, "D64R_Archvile", 1, 0x0FA5, refVile);
			if (madeVile == 0)
			{
				int r2 = 0;
				madeVile = Convert(hellKnight, "D64R_Archvile", 1, 0x0FA6, r2);
				refVile += r2;
			}
			if (dbg && madeVile == 0)
			{
				Console.Printf("d64_ue: %s is listed for an Arch-Vile but has no Baron or Hell Knight to take",
					level.MapName);
			}
		}

		// Spider Mastermind: one, listed maps only, and it must physically fit.
		//
		// Arachnotron first, NOT Cyberdemon. Every Cyberdemon in Retribution is
		// wired to a TID or a special except a single one on MAP33 -- they are
		// all scripted boss fights -- so the handler correctly refuses to touch
		// them and a Cyberdemon-first order just never fires. The Arachnotron is
		// also the closest thing to the Mastermind's footprint that the game
		// actually places (radius 56, the widest non-boss).
		if (MapListed("d64_ue_mastermind_maps", D64R_MM_MAPS))
		{
			madeMM = Convert(arach, "D64R_SpiderMastermind", 1, 0x33D1, refMM);
			if (madeMM == 0)
			{
				int r2 = 0;
				madeMM = Convert(cyber, "D64R_SpiderMastermind", 1, 0x33D2, r2);
				refMM += r2;
			}
			if (madeMM == 0)
			{
				int r3 = 0;
				madeMM = Convert(fatso, "D64R_SpiderMastermind", 1, 0x33D3, r3);
				refMM += r3;
			}
			if (dbg && madeMM == 0)
			{
				Console.Printf("d64_ue: %s -- Mastermind found no spot it fits (refused %d)",
					level.MapName, refMM);
			}
		}

		if (dbg)
		{
			// Pool sizes are printed too: a zero conversion is almost always a
			// map with no donor of that kind rather than a broken selection,
			// and without the pools the two are indistinguishable in the log.
			Console.Printf("d64_ue %s tier %d | pools sgun %d nmimp %d hk %d baron %d cyber %d arach %d",
				level.MapName, tier, poolSgun, poolNmImp, poolHK, poolBaron,
				CountOf(cyber), CountOf(arach));
			Console.Printf("d64_ue %s made | sergeant %d chaingunner %d revenant %d archvile %d mastermind %d | refused %d | monsters %d -> %d",
				level.MapName, madeSgt, madeChain, madeRev, madeVile, madeMM,
				refChain + refSgt + refRev + refVile + refMM,
				before, level.total_monsters);
		}
	}
}
